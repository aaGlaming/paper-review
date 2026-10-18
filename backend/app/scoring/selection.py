"""选档的确定性部分：模型输出解析、原句子串校验、确定性降档守卫。

模型只负责在给定证据里选档；下面三件事由代码完成，不连数据库、不发 HTTP、不导入模型客户端。

- `parse_scoring_json()`：只采纳 `band`、`chunk_id`、`quote`，其余字段（含 `weight`、`score`）一律丢弃；
- `quote_is_substring()`：原句必须是某段父块的**连续子串**，不是分词、不是模糊匹配、不是相似度；
- `apply_mention_guard()`：降档守卫。若该维证据里没有出现题目约束要求必须提到的条件
  （即 `check_type = mention` 的约束），该维不得为「充分」。

守卫完全由数据驱动：关键词读 `constraint.params.keywords`，适用范围读 `constraint.section_types`
与量规维度的 `section_types` 的交集；代码里不出现任何题面字面量。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .aggregate import BANDS, STATUS_INSUFFICIENT

SCORING_TEMPERATURE = 0.2
MAX_CHAT_ATTEMPTS = 2
JSON_FIELDS: tuple[str, ...] = ("band", "chunk_id", "quote")

MENTION_CHECK_TYPE = "mention"
DOWNGRADED_BAND = "基本"
REASON_MENTION_MISSING = "证据里没有提到约束「{name}」"
REASON_NO_KEYWORDS = "约束「{name}」没有给 keywords，无法确定性判定"
REASON_SECTION_MISMATCH = "约束「{name}」的章节类型与这一维不相交，不参与复核"

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


class ScoringParseError(ValueError):
    """模型输出不是约定的 JSON，或缺字段、档位非法。"""


def parse_scoring_json(raw: str) -> dict[str, str]:
    """解析成 {'band', 'chunk_id', 'quote'}。只采纳这三个字段，其余一律忽略。"""
    if not isinstance(raw, str) or not raw.strip():
        raise ScoringParseError("模型没有返回内容")
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScoringParseError(f"不是合法 JSON：{exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ScoringParseError("JSON 顶层必须是对象")
    missing = [field for field in JSON_FIELDS if field not in payload]
    if missing:
        raise ScoringParseError(f"缺字段 {'、'.join(missing)}")
    band = payload["band"]
    if band not in BANDS:
        raise ScoringParseError(f"band 只能是 {'、'.join(BANDS)}")
    quote = payload["quote"]
    if not isinstance(quote, str) or not quote.strip():
        raise ScoringParseError("quote 必须是非空字符串")
    return {"band": str(band), "chunk_id": str(payload["chunk_id"]), "quote": quote}


def quote_is_substring(quote: Any, parents: Iterable[Mapping[str, Any]] | None) -> bool:
    """原句必须逐字出现在某段父块里。"""
    if not isinstance(quote, str) or not quote:
        return False
    return any(quote in str(parent.get("content", "")) for parent in parents or ())


def join_evidence(parents: Iterable[Mapping[str, Any]] | None) -> str:
    """该维的检索证据文本（父块全文拼接），供降档复核使用。"""
    return "\n".join(str(parent.get("content", "")) for parent in parents or ())


def _applies_to_dimension(
    constraint: Mapping[str, Any], dimension_section_types: Sequence[str] | None
) -> bool:
    constraint_types = [str(item) for item in (constraint.get("section_types") or ())]
    dimension_types = [str(item) for item in (dimension_section_types or ())]
    if not constraint_types or not dimension_types:
        return True
    return bool(set(constraint_types) & set(dimension_types))


def apply_mention_guard(
    band: str,
    *,
    evidence_text: str,
    constraints: Iterable[Mapping[str, Any]] | None = None,
    dimension_section_types: Sequence[str] | None = None,
) -> dict[str, Any]:
    """确定性降档：mention 约束没被提到时，该维不得为「充分」。

    返回 `band`（可能已降档）、`downgraded`、`reasons`、`checked`、`skipped`。
    只有「充分」会被降一档；缺 keywords 的约束按无法判定处理并记入 `skipped`，不乱降档。
    """
    outcome: dict[str, Any] = {
        "band": band,
        "downgraded": False,
        "reasons": [],
        "checked": 0,
        "skipped": [],
    }
    if band != BANDS[0]:
        return outcome

    text = str(evidence_text or "")
    for constraint in constraints or ():
        if not isinstance(constraint, Mapping):
            continue
        if str(constraint.get("check_type")) != MENTION_CHECK_TYPE:
            continue
        name = str(constraint.get("name") or "未命名约束")
        if not _applies_to_dimension(constraint, dimension_section_types):
            outcome["skipped"].append(REASON_SECTION_MISMATCH.format(name=name))
            continue
        params = constraint.get("params")
        keywords = []
        if isinstance(params, Mapping):
            keywords = [str(item) for item in (params.get("keywords") or ()) if str(item).strip()]
        if not keywords:
            outcome["skipped"].append(REASON_NO_KEYWORDS.format(name=name))
            continue
        outcome["checked"] += 1
        if not any(keyword in text for keyword in keywords):
            outcome["reasons"].append(REASON_MENTION_MISSING.format(name=name))

    if outcome["reasons"]:
        outcome["band"] = DOWNGRADED_BAND
        outcome["downgraded"] = True
    return outcome


def build_scoring_messages(
    *,
    dimension_code: str,
    dimension_name: str,
    parents: Sequence[Mapping[str, Any]],
    constraints: Iterable[Mapping[str, Any]] | None = None,
    evidence_prompts: Iterable[str] | None = None,
) -> list[dict[str, str]]:
    """拼选档用的 messages。证据逐段编号，编号与 parent_id、chunk_ids 一起给出。"""
    evidence_lines = []
    for index, parent in enumerate(parents, start=1):
        chunk_ids = "、".join(str(item) for item in (parent.get("chunk_ids") or ())) or "无"
        evidence_lines.append(
            f"[{index}] parent_id={parent.get('parent_id')} chunk_ids={chunk_ids}\n"
            f"{parent.get('content', '')}"
        )
    required = [
        f"- {constraint.get('name')}"
        for constraint in constraints or ()
        if isinstance(constraint, Mapping)
        and str(constraint.get("check_type")) == MENTION_CHECK_TYPE
    ] or ["- 无"]
    evidence_points = [f"- {str(item)}" for item in evidence_prompts or () if str(item).strip()] or ["- 无"]

    system = (
        "你是论文预审的选档助手。只输出一个 JSON 对象，字段只有 band、chunk_id、quote。"
        f"band 只能取：{'、'.join(BANDS)}。"
        "quote 必须逐字取自下面给出的父块，是其中某一段的连续子串；"
        "chunk_id 填那段父块的切片编号。不要输出 weight、score 或其他任何字段。"
        f"证据不足时 band 取「{STATUS_INSUFFICIENT}」。"
    )
    user = "\n".join(
        [
            f"维度：{dimension_name}（{dimension_code}）",
            "题目要求必须提到的条件：",
            *required,
            "该维度需要检查的证据要点：",
            *evidence_points,
            "证据（父块全文）：",
            *evidence_lines,
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
