"""Deterministic Markdown artifact extraction; no model or persistence access."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

__all__ = ["extract_artifacts"]


_CITATION_RE = re.compile(r"\[\d+(?:\s*[,，]\s*\d+)*\]")
_HEADING_LINE_RE = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+[^\n]*(?:\n|$)")
_TABLE_SEPARATOR_RE = re.compile(r"^\|\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_SENTENCE_ENDINGS = "。！？；"
_RESULT_TERMS = ("达到", "提升", "降低", "最优", "结论", "结果表明", "因此")


def _is_reference_section(section: Mapping[str, Any]) -> bool:
    title = str(section.get("title") or "")
    section_type = str(section.get("section_type") or "")
    return "参考文献" in title or "参考文献" in section_type


def _validate_sections(markdown: str, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(sections, list):
        raise ValueError("sections 必须是章节列表")
    normalized: list[dict[str, Any]] = []
    for index, section in enumerate(sections):
        if not isinstance(section, Mapping):
            raise ValueError(f"第 {index + 1} 个 section 必须是对象")
        start, end = section.get("char_start"), section.get("char_end")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or start >= end
            or end > len(markdown)
        ):
            raise ValueError(f"第 {index + 1} 个 section 的字符区间无效")
        normalized.append(dict(section))
    return normalized


def _section_for(start: int, sections: list[dict[str, Any]]) -> tuple[int, str | None]:
    for index, section in enumerate(sections):
        if section["char_start"] <= start < section["char_end"]:
            value = section.get("section_type")
            return index, str(value) if value is not None else None
    return -1, None


def _table_ranges(markdown: str) -> list[tuple[int, int]]:
    lines = list(re.finditer(r"(?m)^\|[^\n]*(?:\n|$)", markdown))
    blocks: list[list[re.Match[str]]] = []
    current: list[re.Match[str]] = []
    previous_end: int | None = None
    for line in lines:
        if previous_end == line.start():
            current.append(line)
        else:
            if current:
                blocks.append(current)
            current = [line]
        previous_end = line.end()
    if current:
        blocks.append(current)

    ranges: list[tuple[int, int]] = []
    for block in blocks:
        if any(_TABLE_SEPARATOR_RE.match(line.group(0).rstrip("\r\n")) for line in block):
            ranges.append((block[0].start(), block[-1].end() - len(block[-1].group(0)) + len(block[-1].group(0).rstrip("\r\n"))))
    return ranges


def _line_ranges(markdown: str, pattern: re.Pattern[str]) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in pattern.finditer(markdown)]


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < range_end and end > range_start for range_start, range_end in ranges)


def _claim_candidates(
    markdown: str,
    sections: list[dict[str, Any]],
    excluded: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    counts: dict[int, int] = {}
    # Work paragraph by paragraph. Physical line breaks inside a paragraph stay in the span;
    # blank lines, headings, and table blocks terminate the candidate region.
    lines = list(re.finditer(r"(?m)^.*(?:\n|$)", markdown))
    region_start: int | None = None
    region_parts: list[tuple[int, str]] = []

    def flush_region() -> None:
        nonlocal region_start, region_parts
        if not region_parts:
            region_start, region_parts = None, []
            return
        text = "".join(part for _, part in region_parts)
        base = region_parts[0][0]
        cursor = 0
        for index, char in enumerate(text):
            if char not in _SENTENCE_ENDINGS:
                continue
            candidate = text[cursor : index + 1]
            leading = len(candidate) - len(candidate.lstrip())
            claim = candidate[leading:]
            start = base + cursor + leading
            end = base + index + 1
            if claim:
                section_index, section_type = _section_for(start, sections)
                count = counts.get(section_index, 0)
                reference = section_index >= 0 and _is_reference_section(sections[section_index])
                pure_citation = bool(
                    re.fullmatch(
                        r"(?:\[\d+(?:\s*[,，]\s*\d+)*\]\s*)+[。！？；]?",
                        claim,
                    )
                )
                eligible = (
                    not reference
                    and not pure_citation
                    and 10 <= len(claim) <= 300
                    and (re.search(r"\d", claim) is not None or any(term in claim for term in _RESULT_TERMS))
                    and count < 5
                )
                if eligible:
                    results.append({
                        "artifact_type": "claim",
                        "char_start": start,
                        "char_end": end,
                        "section_type": section_type,
                        "claim_text": claim,
                    })
                    counts[section_index] = count + 1
            cursor = index + 1
        region_start, region_parts = None, []

    for line in lines:
        start, end = line.start(), line.end()
        line_text = line.group(0)
        if not line_text:
            continue
        excluded_line = _overlaps(start, end, excluded)
        blank = not line_text.strip()
        if excluded_line or blank:
            flush_region()
            continue
        if region_start is None:
            region_start = start
        region_parts.append((start, line_text))
    flush_region()
    return results


def extract_artifacts(markdown: str, sections: list[dict]) -> list[dict]:
    """Extract deterministic claim, table, and inline citation records.

    `sections` must provide half-open `char_start`/`char_end` ranges and the
    confirmed `section_type`; artifacts point to exact slices of `markdown`.
    """
    if not isinstance(markdown, str):
        raise ValueError("markdown 必须是字符串")
    valid_sections = _validate_sections(markdown, sections)
    tables = _table_ranges(markdown)
    headings = _line_ranges(markdown, _HEADING_LINE_RE)
    structural_ranges = tables + headings
    items: list[dict[str, Any]] = []

    for start, end in tables:
        section_index, section_type = _section_for(start, valid_sections)
        items.append({
            "artifact_type": "table",
            "char_start": start,
            "char_end": end,
            "section_type": section_type,
            "table_markdown": markdown[start:end],
        })

    for match in _CITATION_RE.finditer(markdown):
        start, end = match.span()
        section_index, section_type = _section_for(start, valid_sections)
        if _overlaps(start, end, structural_ranges):
            continue
        if section_index >= 0 and _is_reference_section(valid_sections[section_index]):
            continue
        items.append({
            "artifact_type": "citation",
            "char_start": start,
            "char_end": end,
            "section_type": section_type,
            "citation_text": match.group(0),
        })

    items.extend(_claim_candidates(markdown, valid_sections, structural_ranges))
    items.sort(key=lambda item: (item["char_start"], item["char_end"], item["artifact_type"]))
    type_field = {"claim": "claim_text", "table": "table_markdown", "citation": "citation_text"}
    for ordinal, item in enumerate(items):
        item["ordinal"] = ordinal
        start, end = item["char_start"], item["char_end"]
        field = type_field[item["artifact_type"]]
        if not (0 <= start < end <= len(markdown)) or markdown[start:end] != item[field]:
            raise ValueError(f"第 {ordinal + 1} 条 {item['artifact_type']} 产物的原文区间校验失败")
    return items
