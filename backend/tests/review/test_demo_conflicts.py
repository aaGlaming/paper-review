# 三篇演示的规则审查测试。
# 只读 data/samples 下的正文与 data/contests 下的约束数据，不访问网络、不读真实 .env、
# 不连数据库、不读向量库，也不调用任何模型。

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.review import consistency, samples  # noqa: E402
from backend.app.review.consistency import (  # noqa: E402
    KIND_CASE_MISSING,
    KIND_CITATION_MISSING,
    KIND_MENTION_MISSING,
    KIND_NUMBER_CONFLICT,
    KIND_RANGE_VIOLATION,
    REGISTERED_CHECKS,
    check_mention,
    check_numbers_citations_ranges,
    check_numeric_range,
    check_required_case,
    find_matches,
    section_spans,
)

SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"
EVAL_DIR = SAMPLES_DIR / "eval"
FORBIDDEN_LITERALS = ("412", "386", "1286", "974", "22.4", "18.6", "160", "[12]", "板凳宽度", "静止")
FORBIDDEN_TOKENS = ("httpx", "requests", "urllib", "aiohttp", "openai", "backend.app.llm", "backend.app.retrieve")
CONTEST_IDS = ("cumcm-2024-A", "cumcm-2024-C", "cumcm-2025-A")


def _text(filename: str) -> str:
    return (SAMPLES_DIR / filename).read_text(encoding="utf-8")


def _constraints(contest_id: str) -> list[dict]:
    payload = json.loads(
        (PROJECT_ROOT / "data" / "contests" / contest_id / "constraints.json").read_text(
            encoding="utf-8"
        )
    )
    return payload["constraints"]


def _findings(filename: str, contest_id: str) -> list[dict]:
    return check_numbers_citations_ranges(_text(filename), _constraints(contest_id))


def _by_kind(findings: list[dict], kind: str) -> list[dict]:
    return [finding for finding in findings if finding["kind"] == kind]


def _evidence_texts(findings: list[dict]) -> list[str]:
    return [item["text"] for finding in findings for item in finding["evidence"]]


def _conflict_with(findings: list[dict], *needles: str) -> dict:
    for finding in _by_kind(findings, KIND_NUMBER_CONFLICT):
        texts = " ".join(item["text"] for item in finding["evidence"])
        if all(needle in texts for needle in needles):
            return finding
    raise AssertionError(f"没有找到同时含 {needles} 的数字冲突：{findings}")


# --- 用例 1-2：板凳龙 ----------------------------------------------------------


def test_bench_dragon_flags_both_termination_times():
    text = _text("bench-dragon.md")

    findings = _findings("bench-dragon.md", "cumcm-2024-A")

    conflict = _conflict_with(findings, "412", "386")
    spans = [(item["char_start"], item["char_end"]) for item in conflict["evidence"]]
    assert len(spans) >= 2
    assert len(set(spans)) == len(spans), "两处偏移必须不同"
    for item in conflict["evidence"]:
        assert text[item["char_start"] : item["char_end"]] == item["text"]
    assert conflict["evidence"][0]["char_start"] != conflict["evidence"][1]["char_start"]


def test_bench_dragon_assumption_sentence_is_locatable():
    text = _text("bench-dragon.md")

    matches = find_matches(text, "忽略板凳宽度")
    assert matches, "样例里必须有这句假设"
    for match in matches:
        assert text[match["char_start"] : match["char_end"]] == "忽略板凳宽度"

    spans = section_spans(text)
    assumption = [span for span in spans if "假设" in span["title"]]
    assert assumption, spans
    assert any(
        assumption[0]["char_start"] <= match["char_start"] < assumption[0]["char_end"]
        for match in matches
    ), "这句假设应当落在假设一节里"


# --- 用例 3-6：烟幕 ------------------------------------------------------------


def test_smoke_flags_both_shielding_durations():
    text = _text("smoke.md")

    findings = _findings("smoke.md", "cumcm-2025-A")

    conflict = _conflict_with(findings, "22.4", "18.6")
    spans = {(item["char_start"], item["char_end"]) for item in conflict["evidence"]}
    assert len(spans) >= 2, "两处偏移必须不同"
    for item in conflict["evidence"]:
        assert text[item["char_start"] : item["char_end"]] == item["text"]


def test_smoke_reports_missing_citation():
    findings = _findings("smoke.md", "cumcm-2025-A")

    missing = _by_kind(findings, KIND_CITATION_MISSING)
    assert missing, findings
    assert any("12" in finding["message"] for finding in missing)
    assert any("12" in item["text"] for finding in missing for item in finding["evidence"])


def test_smoke_flags_uav_speed_out_of_range():
    text = _text("smoke.md")

    findings = _findings("smoke.md", "cumcm-2025-A")

    violations = _by_kind(findings, KIND_RANGE_VIOLATION)
    assert violations, findings
    assert any("160" in item["text"] for finding in violations for item in finding["evidence"])
    for violation in violations:
        assert violation["indicator"]
        for item in violation["evidence"]:
            assert text[item["char_start"] : item["char_end"]] == item["text"]


def test_smoke_does_not_flag_legitimate_numbers():
    findings = _findings("smoke.md", "cumcm-2025-A")

    violations = _by_kind(findings, KIND_RANGE_VIOLATION)
    assert not any("300" in item["text"] for finding in violations for item in finding["evidence"]), (
        "导弹速度 300 m/s 不是无人机速度，不得报越界"
    )

    conflicts = _by_kind(findings, KIND_NUMBER_CONFLICT)
    conflict_texts = _evidence_texts(conflicts)
    for legitimate in ("1.5", "3.6", "20 s"):
        assert not any(legitimate in text for text in conflict_texts), (
            f"{legitimate} 是题目给定的合法取值，不得报成数字冲突"
        )


# --- 用例 7-9：种植 ------------------------------------------------------------


def test_planting_flags_two_revenue_figures():
    text = _text("planting.md")

    findings = _findings("planting.md", "cumcm-2024-C")

    conflict = _conflict_with(findings, "1286", "974")
    spans = {(item["char_start"], item["char_end"]) for item in conflict["evidence"]}
    assert len(spans) >= 2, "两处偏移必须不同"
    for item in conflict["evidence"]:
        assert text[item["char_start"] : item["char_end"]] == item["text"]


def test_planting_reports_missing_legume_requirement():
    findings = _findings("planting.md", "cumcm-2024-C")

    missing = _by_kind(findings, KIND_MENTION_MISSING)
    assert missing, findings
    text = " ".join(finding["message"] for finding in missing)
    assert "豆类" in text
    assert "三年内至少" in text


def test_planting_reports_missing_discount_case():
    findings = _findings("planting.md", "cumcm-2024-C")

    missing = _by_kind(findings, KIND_CASE_MISSING)
    assert missing, findings
    joined = " ".join(finding["message"] for finding in missing)
    assert "result1_2" in joined
    assert not any("result1_1" in json.dumps(finding, ensure_ascii=False) for finding in missing), (
        "滞销情形已经给出，不该报缺 result1_1"
    )


# --- 用例 10：源码约束 ---------------------------------------------------------


def test_review_sources_have_no_sample_literals():
    paths = sorted((PROJECT_ROOT / "backend" / "app" / "review").glob("*.py"))
    assert paths
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for literal in FORBIDDEN_LITERALS:
            assert literal not in source, f"{path}: {literal}"
        for token in FORBIDDEN_TOKENS:
            assert token not in source, f"{path}: {token}"
        for contest_id in CONTEST_IDS:
            assert contest_id not in source, f"{path}: {contest_id}"
        for forbidden in ("if ", "elif "):
            for line in source.splitlines():
                assert not re.search(rf"{forbidden}.*==\s*[\"']\d", line), f"{path}: {line}"


# --- 用例 11-13：评测样例读入与注册检查 ----------------------------------------


def test_eval_papers_load_with_gold_and_expected_findings():
    papers = samples.load_eval_papers(EVAL_DIR)

    assert len(papers) == 12
    ids = {paper["paper_id"] for paper in papers}
    assert len(ids) == 12
    for paper in papers:
        assert paper["text"].strip(), paper["paper_id"]
        assert "自建评测样例" in paper["text"], paper["paper_id"]
        codes = {item["dimension_code"] for item in paper["gold"]}
        assert codes == {
            "assumption",
            "modeling",
            "solution",
            "constraint_check",
            "presentation",
        }, paper["paper_id"]
        assert all(item["band"] in ("充分", "基本", "不足", "证据不足") for item in paper["gold"])
        assert paper["expected_findings"], paper["paper_id"]
        for value in FORBIDDEN_LITERALS:
            assert value not in paper["text"], f"{paper['paper_id']}: {value}"


def test_registered_checks_are_individually_callable():
    assert set(REGISTERED_CHECKS) == {"mention", "numeric_range", "required_case"}

    mention_constraint = {
        "constraint_id": "demo-mention",
        "name": "自建条件",
        "check_type": "mention",
        "params": {"keywords": ["自建关键词"]},
    }
    range_constraint = {
        "constraint_id": "demo-range",
        "name": "自建速度范围为 10～20 m/s",
        "check_type": "numeric_range",
        "params": {"min": 10, "max": 20, "unit": "m/s"},
    }
    case_constraint = {
        "constraint_id": "demo-case",
        "name": "自建情形",
        "check_type": "required_case",
        "params": {"label": "自建情形", "artifact": "result_demo_2"},
    }

    assert check_mention("这里没有那个词", mention_constraint)[0]["kind"] == KIND_MENTION_MISSING
    assert check_mention("这里写了自建关键词", mention_constraint) == []

    violation = check_numeric_range("自建速度范围为 25 m/s", range_constraint)
    assert violation and violation[0]["kind"] == KIND_RANGE_VIOLATION
    assert check_numeric_range("另一台设备的取值为 25 m/s", range_constraint) == []

    assert check_required_case("只给了 result_demo_1", case_constraint)[0]["kind"] == KIND_CASE_MISSING
    assert check_required_case("给出了 result_demo_2", case_constraint) == []

    assert REGISTERED_CHECKS["mention"] is check_mention
    assert REGISTERED_CHECKS["numeric_range"] is check_numeric_range
    assert REGISTERED_CHECKS["required_case"] is check_required_case


def test_findings_shape_is_complete():
    for filename, contest_id in (
        ("bench-dragon.md", "cumcm-2024-A"),
        ("planting.md", "cumcm-2024-C"),
        ("smoke.md", "cumcm-2025-A"),
    ):
        text = _text(filename)
        findings = _findings(filename, contest_id)
        assert findings, filename
        for finding in findings:
            assert finding["kind"] in {
                KIND_NUMBER_CONFLICT,
                KIND_CITATION_MISSING,
                KIND_RANGE_VIOLATION,
                KIND_CASE_MISSING,
                KIND_MENTION_MISSING,
            }
            assert finding.get("constraint_id") or finding.get("indicator")
            assert isinstance(finding["evidence"], list)
            assert finding["message"].strip()
            if finding["kind"] == KIND_NUMBER_CONFLICT:
                assert len(finding["evidence"]) >= 2, "数字冲突至少两处证据"
                spans = {(item["char_start"], item["char_end"]) for item in finding["evidence"]}
                assert len(spans) >= 2
            for item in finding["evidence"]:
                assert text[item["char_start"] : item["char_end"]] == item["text"]
