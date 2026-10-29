from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.app.importing.artifacts import extract_artifacts


SAMPLES = Path("data/samples")


def _sections(markdown: str) -> list[dict[str, object]]:
    headings = list(re.finditer(r"(?m)^#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", markdown))
    spans: list[dict[str, object]] = []
    if not headings:
        return [{"char_start": 0, "char_end": len(markdown), "section_type": "未分类"}]
    if headings[0].start() > 0:
        spans.append({"char_start": 0, "char_end": headings[0].start(), "section_type": "未分类"})
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        title = heading.group(1)
        spans.append({
            "char_start": heading.start(),
            "char_end": end,
            "section_type": "参考文献" if "参考文献" in title else title,
        })
    return spans


def _sample(name: str) -> tuple[str, list[dict[str, object]]]:
    text = (SAMPLES / name).read_text(encoding="utf-8")
    return text, _sections(text)


def test_extracts_planting_markdown_table_verbatim():
    markdown, sections = _sample("planting.md")
    items = extract_artifacts(markdown, sections)
    tables = [item for item in items if item["artifact_type"] == "table"]

    assert len(tables) == 1
    table = tables[0]
    assert table["table_markdown"] == "| 项目 | 数值 |\n| --- | --- |\n| 七年总收益（万元） | 974 万元 |\n| 求解状态 | 最优 |"
    assert markdown[table["char_start"] : table["char_end"]] == table["table_markdown"]


def test_sentence_mentioning_table_does_not_create_table_artifact():
    markdown = "正文提到表 1 给出结果，但这里没有表格结构。"
    items = extract_artifacts(markdown, _sections(markdown))
    assert not [item for item in items if item["artifact_type"] == "table"]


def test_extracts_inline_citation_but_not_reference_entries():
    markdown, sections = _sample("smoke.md")
    citations = [item for item in extract_artifacts(markdown, sections) if item["artifact_type"] == "citation"]

    assert [item["citation_text"] for item in citations] == ["[12]"]
    assert "参考文献" not in markdown[citations[0]["char_start"] : citations[0]["char_end"]]


def test_extracts_both_conflicting_smoke_results_without_deduplication():
    markdown, sections = _sample("smoke.md")
    claims = [item["claim_text"] for item in extract_artifacts(markdown, sections) if item["artifact_type"] == "claim"]

    result_claims = [claim for claim in claims if "22.4 s" in claim or "18.6 s" in claim]
    assert len(result_claims) == 2
    assert "22.4 s" in result_claims[0]
    assert "18.6 s" in result_claims[1]


def test_disclaimer_is_not_extracted_as_claim():
    markdown, sections = _sample("smoke.md")
    claims = [item["claim_text"] for item in extract_artifacts(markdown, sections) if item["artifact_type"] == "claim"]
    assert not any("演示样例" in claim for claim in claims)


def test_every_artifact_span_matches_its_type_specific_text_and_ordinals_are_stable():
    markdown, sections = _sample("planting.md")
    items = extract_artifacts(markdown, sections)
    field_by_type = {"claim": "claim_text", "table": "table_markdown", "citation": "citation_text"}

    assert [item["ordinal"] for item in items] == list(range(len(items)))
    assert [item["char_start"] for item in items] == sorted(item["char_start"] for item in items)
    for item in items:
        start, end = item["char_start"], item["char_end"]
        assert 0 <= start < end <= len(markdown)
        assert markdown[start:end] == item[field_by_type[item["artifact_type"]]]


def test_headingless_text_uses_unclassified_section():
    markdown = "这一段共有足够长度并得到 12 个结果。"
    items = extract_artifacts(markdown, _sections(markdown))
    assert items
    assert {item["section_type"] for item in items} == {"未分类"}


def test_long_pure_citation_sentence_is_not_a_claim():
    markdown = "[1, 2, 3, 4, 5, 6]。"
    items = extract_artifacts(markdown, _sections(markdown))
    assert [item["artifact_type"] for item in items] == ["citation"]


def test_claim_extraction_is_capped_at_five_per_section():
    markdown = "\n".join(f"本研究结果表明第{i}项方案达到预期效果。" for i in range(1, 7))
    items = extract_artifacts(markdown, _sections(markdown))
    assert len([item for item in items if item["artifact_type"] == "claim"]) == 5


def test_malformed_section_ranges_raise_readable_error():
    with pytest.raises(ValueError, match="section"):
        extract_artifacts("一段有结果的文本达到 12 项。", [{"char_start": 3, "char_end": 2}])
