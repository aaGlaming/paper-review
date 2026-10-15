"""修改清单：只转写已有的维度档位与审查结果。

不另写褒贬，也不生成新结论：清单里的每一项都能指回一条上游记录。
排序固定，不得调换：**题目约束和数字冲突 → 证据不足 → 表述**。
每条建议带上游 id：维度类指向 `dimension_code`，审查类指向该条 finding 的 `kind` 与标识
（`constraint_id` 或 `indicator`）。把上游记录删掉后，再调 `build_change_list()` 该条建议不再出现。

`引用失败` 的维度不进本清单：它既不是题目约束冲突，也不是证据不足，按 v0.8.0 的三段顺序
没有它的位置，由评分状态单独呈现。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

SECTION_CONSTRAINTS = "题目约束与数字冲突"
SECTION_INSUFFICIENT = "证据不足"
SECTION_PRESENTATION = "表述"
SECTION_ORDER: tuple[str, ...] = (SECTION_CONSTRAINTS, SECTION_INSUFFICIENT, SECTION_PRESENTATION)

KIND_NUMBER_CONFLICT = "数字冲突"
KIND_CONSTRAINT = "题目约束"
KIND_INSUFFICIENT = "证据不足"
KIND_PRESENTATION = "表述"

# 审查结果按类型并到两段里：数字冲突独占一类，其余都算题目约束。
FINDING_KIND_TO_KIND: dict[str, str] = {
    "数字冲突": KIND_NUMBER_CONFLICT,
    "越界": KIND_CONSTRAINT,
    "未提到条件": KIND_CONSTRAINT,
    "缺少情形": KIND_CONSTRAINT,
    "引用缺失": KIND_CONSTRAINT,
}

ACTION_BY_FINDING_KIND: dict[str, str] = {
    "数字冲突": "把两处数值改成同一口径，并在正文说明取值来源",
    "越界": "把取值改回题目给定范围，或在正文说明超出范围的理由",
    "未提到条件": "在假设或模型一节补上这条题目条件",
    "缺少情形": "补上该情形的结果文件与对应方案表",
    "引用缺失": "把缺的条目补进参考文献列表，或删掉正文里的引用",
}
ACTION_INSUFFICIENT = "在对应章节补上可引用的原句与推导，或按现有证据把这一维降到相邻档位"
ACTION_PRESENTATION = "按问题顺序重排结果，补齐单位、图表编号与引用"

PRESENTATION_DIMENSION = "presentation"
INSUFFICIENT_BAND = "证据不足"
WORDING_BANDS: tuple[str, ...] = ("基本", "不足")

# 报告文本与接口 JSON 一律不得出现这些字样。
AWARD_WORDS: tuple[str, ...] = ("一等奖", "二等奖", "三等奖", "获奖概率", "获奖", "名次")


def contains_award_words(text: Any) -> bool:
    """报告文本或接口响应里是否出现奖项字样。"""
    content = str(text)
    return any(word in content for word in AWARD_WORDS)


def _dimension_name(code: str, dimensions: Mapping[str, str] | None) -> str:
    if dimensions and code in dimensions:
        return str(dimensions[code])
    return code


def _name_table(dimensions: Iterable[Mapping[str, Any]] | None) -> dict[str, str]:
    table: dict[str, str] = {}
    for item in dimensions or ():
        if not isinstance(item, Mapping):
            continue
        code = str(item.get("dimension_code") or item.get("code") or "")
        if code:
            table[code] = str(item.get("name") or code)
    return table


def _normalize_results(dimension_results: Any) -> list[dict[str, Any]]:
    if isinstance(dimension_results, Mapping):
        items = [
            {"dimension_code": code, **(value if isinstance(value, Mapping) else {})}
            for code, value in dimension_results.items()
        ]
    else:
        items = list(dimension_results or ())
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        code = str(item.get("dimension_code") or item.get("code") or "")
        if not code:
            continue
        normalized.append(
            {
                "dimension_code": code,
                "band": item.get("band"),
                "status": item.get("status") or item.get("band"),
                "quote": item.get("quote"),
                "chunk_ids": [str(chunk) for chunk in (item.get("chunk_ids") or ())],
            }
        )
    return normalized


def _evidence_entry(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "text": result.get("quote") or "",
        "band": result.get("band"),
        "status": result.get("status"),
        "chunk_ids": list(result.get("chunk_ids") or ()),
    }


def build_change_list(
    dimension_results: Any = None,
    findings: Iterable[Mapping[str, Any]] | None = None,
    dimensions: Iterable[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """把已校验的审查结果与维度档位转成修改清单。"""
    names = _name_table(dimensions)
    items: list[dict[str, Any]] = []

    for finding in findings or ():
        if not isinstance(finding, Mapping):
            continue
        finding_kind = str(finding.get("kind") or "")
        kind = FINDING_KIND_TO_KIND.get(finding_kind)
        if kind is None:
            continue
        identifier = str(finding.get("constraint_id") or finding.get("indicator") or "")
        items.append(
            {
                "section": SECTION_CONSTRAINTS,
                "kind": kind,
                "finding_kind": finding_kind,
                "upstream_id": f"finding:{finding_kind}:{identifier}",
                "target": str(finding.get("indicator") or finding.get("constraint_id") or ""),
                "evidence": [dict(entry) for entry in (finding.get("evidence") or ())],
                "action": ACTION_BY_FINDING_KIND.get(finding_kind, ACTION_INSUFFICIENT),
            }
        )

    for result in _normalize_results(dimension_results):
        code = result["dimension_code"]
        band = result["band"]
        if band == INSUFFICIENT_BAND:
            items.append(
                {
                    "section": SECTION_INSUFFICIENT,
                    "kind": KIND_INSUFFICIENT,
                    "upstream_id": f"dimension:{code}",
                    "dimension_code": code,
                    "target": _dimension_name(code, names),
                    "evidence": [_evidence_entry(result)],
                    "action": ACTION_INSUFFICIENT,
                }
            )

    for result in _normalize_results(dimension_results):
        code = result["dimension_code"]
        if code != PRESENTATION_DIMENSION or result["band"] not in WORDING_BANDS:
            continue
        items.append(
            {
                "section": SECTION_PRESENTATION,
                "kind": KIND_PRESENTATION,
                "upstream_id": f"dimension:{code}",
                "dimension_code": code,
                "target": _dimension_name(code, names),
                "evidence": [_evidence_entry(result)],
                "action": ACTION_PRESENTATION,
            }
        )

    return sorted(items, key=lambda item: SECTION_ORDER.index(item["section"]))


def render_change_list(items: Iterable[Mapping[str, Any]]) -> str:
    """把清单渲染成纯文本（页面与测试都用它检查字样）。"""
    materialized = list(items or ())
    lines: list[str] = []
    for section in SECTION_ORDER:
        group = [item for item in materialized if item.get("section") == section]
        if not group:
            continue
        lines.append(f"## {section}")
        for item in group:
            target = item.get("target") or item.get("upstream_id")
            lines.append(f"- [{item.get('kind')}] {target}（上游 {item.get('upstream_id')}）：{item.get('action')}")
            for entry in item.get("evidence") or ():
                text = str(entry.get("text") or "").strip()
                if text:
                    lines.append(f"  证据：{text}")
    return "\n".join(lines)
