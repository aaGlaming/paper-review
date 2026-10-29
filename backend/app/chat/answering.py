"""基于已索引评审片段回答教师问询，并校验模型返回的记录引用。"""

from __future__ import annotations

import os
import re
from typing import Any, Callable

from ..llm.client import LLMResponseError
from . import records, retrieval


SYSTEM_PROMPT = """你是竞赛论文预审工作台的记录助手，只能依据下面提供的评审记录片段回答问题。
1. 不得编造片段里没有的事实；片段不足以回答时，直接说“这些记录里没有相关信息”。
2. 每条结论后面必须用 [review_id=xxx dim=yyy] 标注它来自哪条记录的哪个维度，格式照抄。
3. 不输出奖项、名次、获奖概率等推测性评价。
4. 用中文回答，控制在 300 字以内，先给结论再给依据。"""

EMPTY_RETRIEVAL_CONTENT = "这些记录里没有相关信息。可以换一个说法，或确认赛题范围是否正确。"
RECORD_NOT_FOUND_CONTENT = "找不到该记录编号对应的评审内容，请确认编号是否正确或该记录是否已归档。"
_CITATION_RE = re.compile(r"\[review_id=([^\]\s]+)\s+dim=([^\]\s]+)\]")
_BAND_RE = re.compile(r"【档位】([^\r\n【]*)")


class AnswerError(RuntimeError):
    """模型在一次重试后仍未能生成回答。"""


def failure_reason(error: AnswerError) -> str:
    if str(error) == "检索失败，请稍后重试":
        return "retrieval_failed"
    cause = error.__cause__
    if cause is not None and type(cause).__name__ == "LLMConfigError":
        return "not_found_model"
    return "both_attempts_failed"


def validate_citations(
    content: str,
    available: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[str, list[dict[str, str]], list[dict[str, str]], int]:
    """只保留检索结果中存在的引用，并统计无效与未使用片段。"""
    allowed: set[tuple[str, str]] = {
        (str(item.get("review_id", "")), str(item.get("dimension_code", "")))
        for item in available
        if item.get("citable", True)
    }
    cited: list[tuple[str, str]] = []
    rejected: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        pair = (match.group(1), match.group(2))
        if pair not in allowed:
            if pair not in rejected:
                rejected.append(pair)
            return ""
        if pair not in cited:
            cited.append(pair)
        return match.group(0)

    cleaned = _CITATION_RE.sub(replace, content)
    refs = [{"review_id": review_id, "dimension_code": dimension_code}
            for review_id, dimension_code in cited]
    rejected_refs = [{"review_id": review_id, "dimension_code": dimension_code}
                     for review_id, dimension_code in rejected]
    unused = len(allowed.difference(cited))
    return cleaned, refs, rejected_refs, unused


def _default_chat_fn(messages: list[dict[str, str]]) -> str:
    from ..llm.client import chat

    return chat(messages)


def call_chat_with_retry(
    messages: list[dict[str, str]],
    chat_fn: Callable[[list[dict[str, str]]], str] | None = None,
) -> str:
    caller = chat_fn or _default_chat_fn
    try:
        return caller(messages)
    except Exception:
        try:
            return caller(messages)
        except Exception as exc:
            raise AnswerError("问询失败，请重试") from exc


def _prompt_content(question: str, records: list[dict[str, Any]]) -> str:
    chunks = ["【可用记录片段】"]
    for index, item in enumerate(records, start=1):
        content = str(item.get("content") or "")[:800]
        band_match = _BAND_RE.search(content)
        band = band_match.group(1).strip() if band_match else "未标注"
        chunks.append(
            f"[{index}] review_id={item.get('review_id', '')} "
            f"dim={item.get('dimension_code', '')} 档位={band}\n{content}"
        )
    chunks.append(f"【问题】{question}")
    return "\n\n".join(chunks)


def answer_question(
    session_db,
    *,
    session_row,
    question: str,
    contest_id: str,
    search_fn: Callable[..., list[dict[str, Any]]] | None = None,
    chat_fn: Callable[[list[dict[str, str]]], str] | None = None,
) -> dict[str, Any]:
    """检索并回答；定点记录只用其自身块，避免混入其他记录成为依据。"""
    del session_row  # 接口保留会话上下文，持久化由事务型路由统一处理。
    target_review = retrieval.extract_review_id(question) or ""
    mode = "vector"
    direct_count = 0
    if target_review:
        direct_records = records.load_record_blocks(target_review, session=session_db)
        if not direct_records:
            return {
                "content": RECORD_NOT_FOUND_CONTENT,
                "refs": [],
                "model_name": os.environ.get("LLM_MODEL", "").strip(),
                "notes": {
                    "mode": "record_missing", "target_review": target_review, "direct": 0,
                    "retrieved": 0, "model_called": False, "rejected": [], "unused": 0,
                },
            }
        mode = "record"
        direct_count = len(direct_records)
        records_for_prompt = direct_records
    else:
        searcher = search_fn or retrieval.search_records
        try:
            records_for_prompt = list(searcher(question, contest_id=contest_id, limit=8) or [])[:8]
        except LLMResponseError as exc:
            raise AnswerError("检索失败，请稍后重试") from exc
    available_records = records_for_prompt
    if not available_records:
        return {
            "content": EMPTY_RETRIEVAL_CONTENT,
            "refs": [],
            "model_name": os.environ.get("LLM_MODEL", "").strip(),
            "notes": {"mode": mode, "target_review": target_review, "direct": direct_count,
                      "retrieved": 0, "model_called": False, "rejected": [], "unused": 0},
        }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _prompt_content(question, available_records)},
    ]
    raw_answer = call_chat_with_retry(messages, chat_fn)
    content, refs, rejected, unused = validate_citations(str(raw_answer), available_records)
    return {
        "content": content,
        "refs": refs,
        "model_name": os.environ.get("LLM_MODEL", "").strip(),
        "notes": {
            "mode": mode, "target_review": target_review, "direct": direct_count,
            "retrieved": len(available_records), "model_called": True,
            "rejected": rejected, "unused": unused, "cited": len(refs),
        },
    }
