"""预审状态图（v0.6.0：章节确认、逐维检索、选档与加总）。

固定顺序：parse → confirm → retrieve → score → END。
- parse：按 ATX 标题规则（`#` ～ `######`）切出章节树，产出后 status = 待确认。
- confirm：调用 interrupt() 把章节树交给调用方，收到 Command(resume=...) 的答复后覆盖类型。
  resume 之后不重新解析章节树。
- retrieve：按量规维度逐维检索（每个 dimension_code 各一次），把该维的父块列表与状态
  （命中 / 证据不足）写进状态。检索器可注入；没有注入时按「证据不足」记账，不假装命中。
- score：分两路。注入了 `chat` 时逐维选档并按量规权重加总；没有注入时保持占位行为，
  只把 score_node_calls 加 1 并令 status = 完成，不选档、不报错。

模型只能从外面注入一个 `chat` 可调用对象；本模块不导入模型客户端，也不负责网络请求。
选档的确定性部分（JSON 解析、原句子串校验、降档守卫、加权合计）在 `backend/app/scoring`。
检查点用 InMemorySaver，thread_id 取 review_id；只有带检查点的图支持 interrupt/resume。
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ..importing.catalog import DIMENSION_CODES as RUBRIC_DIMENSION_CODES
from ..retrieve.three_route import DIMENSION_STATUSES, MAX_PARENTS, STATUS_INSUFFICIENT
from ..scoring.aggregate import STATUS_CITATION_FAILURE, STATUS_FAILURE, weighted_sum
from ..scoring.selection import (
    MAX_CHAT_ATTEMPTS,
    SCORING_TEMPERATURE,
    ScoringParseError,
    apply_mention_guard,
    build_scoring_messages,
    join_evidence,
    parse_scoring_json,
    quote_is_substring,
)

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

__all__ = [
    "REVIEW_STATUSES",
    "SECTION_TYPES",
    "UNCLASSIFIED_SECTION_TYPE",
    "EmptyPaperError",
    "RetrieveRequest",
    "ReviewState",
    "build_review_graph",
    "create_review",
    "default_retriever",
    "resume_review",
]

# 评审单状态只有这五个，不得再添「已获奖」之类的状态。
REVIEW_STATUSES: tuple[str, ...] = ("草稿解析", "待确认", "评分中", "完成", "失败")

# 章节类型只有这六个，切不出类型的标题归入「未分类」。
SECTION_TYPES: tuple[str, ...] = ("假设", "模型", "求解", "结果", "检验", "参考文献")
UNCLASSIFIED_SECTION_TYPE = "未分类"

STATUS_DRAFTING = REVIEW_STATUSES[0]
STATUS_PENDING = REVIEW_STATUSES[1]
STATUS_SCORING = REVIEW_STATUSES[2]
STATUS_DONE = REVIEW_STATUSES[3]

_HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)

# 标题里出现这些词就归到对应类型。同一标题命中多个词时，取结束位置最靠后的那个：
# 「模型假设」→ 假设，「模型求解」→ 求解，「模型检验」→ 检验。
_SECTION_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("假设", ("假设",)),
    ("求解", ("求解",)),
    ("检验", ("检验",)),
    ("结果", ("结果",)),
    ("模型", ("模型", "建模")),
)
_REFERENCES_KEYWORDS: tuple[str, ...] = ("参考文献", "references", "bibliography")

PREAMBLE_TITLE = "开头正文"


class EmptyPaperError(ValueError):
    """论文文本为空或全是空白。此时不创建评审，也不产生 review_id。"""


@dataclass(frozen=True)
class RetrieveRequest:
    """一次逐维检索的入参：哪个评审单、哪一维、绑定了哪道题与哪版量规。"""

    review_id: str
    dimension_code: str
    contest_id: str | None = None
    rubric_id: str | None = None
    section_types: tuple[str, ...] = ()


class ReviewState(TypedDict, total=False):
    review_id: str
    paper_text: str
    sections: list[dict[str, Any]]
    confirmed: bool
    status: str
    score_node_calls: int
    parse_node_calls: int
    # v0.5.0：赛题与量规绑定、逐维检索结果与检索节点调用计数
    contest_id: str | None
    rubric_id: str | None
    retrieve_section_types: list[str]
    retrievals: dict[str, Any]
    retrieve_node_calls: int
    # v0.6.0：选档输入（赛题约束数据）与输出（每维结果、加总）
    constraints: list[dict[str, Any]]
    dimension_results: dict[str, Any]
    score: dict[str, Any]


def _classify(title: str) -> str:
    """按标题文字判类型。判不出来返回「未分类」，不新造类型。"""
    normalized = title.strip().lower()
    for keyword in _REFERENCES_KEYWORDS:
        if keyword in normalized:
            return "参考文献"
    best_type = UNCLASSIFIED_SECTION_TYPE
    best_end = -1
    for section_type, keywords in _SECTION_KEYWORDS:
        for keyword in keywords:
            index = normalized.find(keyword)
            if index < 0:
                continue
            end = index + len(keyword)
            if end > best_end:
                best_end = end
                best_type = section_type
    return best_type


def _parse_sections(paper_text: str) -> list[dict[str, Any]]:
    """按 ATX 标题切章节树。第一个标题之前的非空正文单独成一条「未分类」。"""
    matches = list(_HEADING_RE.finditer(paper_text))
    sections: list[dict[str, Any]] = []
    preamble = paper_text[: matches[0].start()].strip() if matches else paper_text.strip()
    if preamble:
        sections.append(
            {
                "title": PREAMBLE_TITLE,
                "section_type": UNCLASSIFIED_SECTION_TYPE,
                "level": 0,
                "content": preamble,
            }
        )
    for index, match in enumerate(matches):
        title = match.group(2).strip()
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(paper_text)
        sections.append(
            {
                "title": title,
                "section_type": _classify(title),
                "level": len(match.group(1)),
                "content": paper_text[match.end() : content_end].strip(),
            }
        )
    return sections


def _sections_from_answer(answer: Any, current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """取出调用方在 Command(resume=...) 里给的章节类型，原样采用，不重新解析。"""
    if isinstance(answer, dict):
        if "sections" not in answer:
            raise ValueError("章节确认的答复缺少 sections")
        sections = answer["sections"]
    elif isinstance(answer, list):
        sections = answer
    else:
        raise ValueError("章节确认的答复必须是 {\"sections\": [...]} 或列表")
    if not isinstance(sections, list):
        raise ValueError("章节确认的 sections 必须是列表")
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("章节树里的每一项都必须是对象")
    return [dict(section) for section in sections]


def _parse_node(state: ReviewState) -> dict[str, Any]:
    sections = _parse_sections(state.get("paper_text", ""))
    return {
        "sections": sections,
        "status": STATUS_PENDING,
        "parse_node_calls": state.get("parse_node_calls", 0) + 1,
    }


def _confirm_node(state: ReviewState) -> dict[str, Any]:
    answer = interrupt(
        {
            "review_id": state.get("review_id", ""),
            "status": STATUS_PENDING,
            "sections": state.get("sections", []),
        }
    )
    sections = _sections_from_answer(answer, state.get("sections", []))
    return {"sections": sections, "confirmed": True, "status": STATUS_SCORING}


def _score_node(state: ReviewState) -> dict[str, Any]:
    """占位节点：本版不评分，只记一次调用。"""
    return {
        "score_node_calls": state.get("score_node_calls", 0) + 1,
        "status": STATUS_DONE,
    }


def default_retriever(request: RetrieveRequest) -> dict[str, Any]:
    """没有注入检索器时的缺省行为：不做任何检索，该维直接记「证据不足」，不假装命中。"""
    return {
        "status": STATUS_INSUFFICIENT,
        "rounds": 0,
        "parents": [],
        "queries": [],
        "reason": "未注入检索器",
    }


def _parent_to_dict(parent: Any) -> dict[str, Any]:
    if isinstance(parent, Mapping):
        return dict(parent)
    return {
        "parent_id": getattr(parent, "parent_id", ""),
        "section_type": getattr(parent, "section_type", ""),
        "content": getattr(parent, "content", ""),
        "review_id": getattr(parent, "review_id", None),
        "chunk_ids": list(getattr(parent, "chunk_ids", ()) or ()),
    }


def _normalize_outcome(outcome: Any) -> dict[str, Any]:
    """把检索层返回的对象或字典统一成状态里能存的结构。"""
    if isinstance(outcome, Mapping):
        status = str(outcome.get("status", ""))
        rounds = int(outcome.get("rounds", 0) or 0)
        parents = list(outcome.get("parents") or [])
        queries = list(outcome.get("queries") or [])
        reason = outcome.get("reason")
    else:
        status = str(getattr(outcome, "status", ""))
        rounds = int(getattr(outcome, "rounds", 0) or 0)
        parents = list(getattr(outcome, "parents", ()) or ())
        queries = list(getattr(outcome, "queries", ()) or ())
        reason = getattr(outcome, "reason", None)
    if status not in DIMENSION_STATUSES:
        raise ValueError(f"维度状态只能是 {'、'.join(DIMENSION_STATUSES)}，收到 {status!r}")
    normalized: dict[str, Any] = {
        "status": status,
        "rounds": rounds,
        "queries": [str(query) for query in queries],
        "parents": [_parent_to_dict(parent) for parent in parents],
    }
    if reason:
        normalized["reason"] = str(reason)
    return normalized


def _retrieve_node_factory(
    retriever: Callable[[RetrieveRequest], Any] | None,
    dimensions: Sequence[str],
) -> Callable[[ReviewState], dict[str, Any]]:
    def retrieve_node(state: ReviewState) -> dict[str, Any]:
        results: dict[str, Any] = {}
        section_types = tuple(str(item) for item in (state.get("retrieve_section_types") or ()))
        for dimension_code in dimensions:
            request = RetrieveRequest(
                review_id=state.get("review_id", ""),
                dimension_code=dimension_code,
                contest_id=state.get("contest_id"),
                rubric_id=state.get("rubric_id"),
                section_types=section_types,
            )
            outcome = retriever(request) if retriever is not None else default_retriever(request)
            results[dimension_code] = _normalize_outcome(outcome)
        return {
            "retrievals": results,
            "status": STATUS_SCORING,
            "retrieve_node_calls": state.get("retrieve_node_calls", 0) + 1,
        }

    return retrieve_node


def _dimension_code_of(dimension: Mapping[str, Any]) -> str:
    return str(dimension.get("dimension_code") or dimension.get("code") or "")


def _normalize_rubric_dimensions(
    rubric_dimensions: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, Any], ...]:
    """量规维度：至少含 dimension_code 与 weight，可另带 name、section_types。"""
    normalized: list[dict[str, Any]] = []
    for dimension in rubric_dimensions or ():
        if not isinstance(dimension, Mapping):
            raise ValueError("rubric_dimensions 的每一项都必须是对象")
        code = _dimension_code_of(dimension)
        if not code:
            raise ValueError("rubric_dimensions 的每一项都要有 dimension_code")
        weight = dimension.get("weight", 0)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            weight = 0
        normalized.append(
            {
                "dimension_code": code,
                "name": str(dimension.get("name") or code),
                "weight": int(weight),
                "section_types": [str(item) for item in (dimension.get("section_types") or ())],
                "evidence_prompts": [str(item) for item in (dimension.get("evidence_prompts") or ())],
            }
        )
    return tuple(normalized)


def _score_dimension(
    chat: Callable[..., str],
    dimension: Mapping[str, Any],
    parents: Sequence[Mapping[str, Any]],
    constraints: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """一个维度的选档：检索为空记证据不足；JSON 解析失败重试一次；原句不是子串记引用失败。"""
    code = _dimension_code_of(dimension)
    if not parents:
        return {
            "dimension_code": code,
            "band": STATUS_INSUFFICIENT,
            "status": STATUS_INSUFFICIENT,
            "chunk_ids": [],
            "quote": None,
            "reason": "检索为空：该维证据不足",
        }

    messages = build_scoring_messages(
        dimension_code=code,
        dimension_name=str(dimension.get("name") or code),
        parents=parents,
        constraints=constraints,
        evidence_prompts=dimension.get("evidence_prompts") or (),
    )
    parsed: dict[str, str] | None = None
    attempts = 0
    failure_reason = ""
    while attempts < MAX_CHAT_ATTEMPTS:
        attempts += 1
        try:
            parsed = parse_scoring_json(chat(messages, SCORING_TEMPERATURE))
        except ScoringParseError as exc:
            parsed = None
            failure_reason = f"模型输出不是约定 JSON：{exc}"
        except Exception as exc:  # 模型调用本身出错也照样重试一次，不让整单崩掉
            parsed = None
            failure_reason = f"选档调用出错：{type(exc).__name__}"
        if parsed is not None:
            break

    if parsed is None:
        return {
            "dimension_code": code,
            "band": None,
            "status": STATUS_FAILURE,
            "chunk_ids": [],
            "quote": None,
            "reason": failure_reason or "模型输出不是约定 JSON",
            "chat_calls": attempts,
        }

    if parsed["band"] == STATUS_INSUFFICIENT:
        return {
            "dimension_code": code,
            "band": STATUS_INSUFFICIENT,
            "status": STATUS_INSUFFICIENT,
            "chunk_ids": [],
            "quote": None,
            "reason": "模型在给定证据里没有找到可引用的原句",
            "chat_calls": attempts,
        }

    if not quote_is_substring(parsed["quote"], parents):
        return {
            "dimension_code": code,
            "band": parsed["band"],
            "status": STATUS_CITATION_FAILURE,
            "chunk_ids": [parsed["chunk_id"]],
            "quote": parsed["quote"],
            "reason": "原句不是父块连续子串",
            "chat_calls": attempts,
        }

    guard = apply_mention_guard(
        parsed["band"],
        evidence_text=join_evidence(parents),
        constraints=constraints,
        dimension_section_types=dimension.get("section_types"),
    )
    return {
        "dimension_code": code,
        "band": guard["band"],
        "status": guard["band"],
        "chunk_ids": [parsed["chunk_id"]],
        "quote": parsed["quote"],
        "guard": guard,
        "chat_calls": attempts,
    }


def _make_score_node(
    chat: Callable[..., str] | None,
    rubric_dimensions: Sequence[Mapping[str, Any]],
    constraints: Sequence[Mapping[str, Any]],
) -> Callable[[ReviewState], dict[str, Any]]:
    def score_node(state: ReviewState) -> dict[str, Any]:
        calls = state.get("score_node_calls", 0) + 1
        if chat is None:
            # 没有注入模型：沿用占位节点，不选档、不报错。
            return _score_node(state)

        resolved_constraints = tuple(constraints or state.get("constraints") or ())
        retrievals = state.get("retrievals") or {}
        results: dict[str, Any] = {}
        for dimension in rubric_dimensions:
            code = _dimension_code_of(dimension)
            parents = list(((retrievals.get(code) or {}).get("parents") or ()))[:MAX_PARENTS]
            results[code] = _score_dimension(chat, dimension, parents, resolved_constraints)
        return {
            "dimension_results": results,
            "score": weighted_sum(rubric_dimensions, list(results.values())),
            "score_node_calls": calls,
            "status": STATUS_DONE,
        }

    return score_node


def _require_checkpointer(graph: Any) -> None:
    if getattr(graph, "checkpointer", None) is None:
        raise ValueError("本版的状态图必须带检查点，请用 build_review_graph() 编译后再调用")


def build_review_graph(
    checkpointer: "BaseCheckpointSaver | None" = None,
    *,
    retriever: Callable[[RetrieveRequest], Any] | None = None,
    dimensions: Sequence[str] | None = None,
    chat: Callable[..., str] | None = None,
    rubric_dimensions: Sequence[Mapping[str, Any]] | None = None,
    constraints: Sequence[Mapping[str, Any]] | None = None,
) -> "CompiledStateGraph":
    """编译预审状态图。不传检查点时默认用 InMemorySaver，检查点键为 review_id。

    `retriever` 是逐维检索的可调用对象；缺省时每维记「证据不足」，不发请求、不调模型。
    `chat` 是选档用的模型调用（签名与 `backend/app/llm/client.py` 的 `chat()` 一致），
    缺省时评分节点保持占位行为：只累加 score_node_calls、status 记「完成」，不选档、不报错。
    注入 `chat` 时必须同时给 `rubric_dimensions`（含 dimension_code 与 weight），否则无法按量规加总。
    `constraints` 是赛题约束数据，供选档后的确定性降档复核使用。
    """
    resolved_rubric = _normalize_rubric_dimensions(rubric_dimensions)
    if chat is not None and not resolved_rubric:
        raise ValueError("注入了 chat 时必须同时给 rubric_dimensions，否则无法按量规权重加总")
    resolved_constraints = tuple(constraints or ())
    if dimensions is not None:
        resolved_dimensions = tuple(dimensions)
    elif resolved_rubric:
        resolved_dimensions = tuple(item["dimension_code"] for item in resolved_rubric)
    else:
        resolved_dimensions = tuple(RUBRIC_DIMENSION_CODES)

    builder = StateGraph(ReviewState)
    builder.add_node("parse", _parse_node)
    builder.add_node("confirm", _confirm_node)
    builder.add_node("retrieve", _retrieve_node_factory(retriever, resolved_dimensions))
    builder.add_node("score", _make_score_node(chat, resolved_rubric, resolved_constraints))
    builder.add_edge(START, "parse")
    builder.add_edge("parse", "confirm")
    builder.add_edge("confirm", "retrieve")
    builder.add_edge("retrieve", "score")
    builder.add_edge("score", END)
    if checkpointer is None:
        checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


_DEFAULT_GRAPH: "CompiledStateGraph | None" = None


def _default_graph() -> "CompiledStateGraph":
    global _DEFAULT_GRAPH
    if _DEFAULT_GRAPH is None:
        _DEFAULT_GRAPH = build_review_graph()
    return _DEFAULT_GRAPH


def create_review(paper_text: str, review_id: str | None = None, *, graph: Any = None) -> str:
    """创建评审并推进到确认节点。空文本立刻抛 EmptyPaperError，不产生 review_id。"""
    if not isinstance(paper_text, str) or not paper_text.strip():
        raise EmptyPaperError("论文文本为空或全是空白，不创建评审")
    resolved_graph = graph if graph is not None else _default_graph()
    _require_checkpointer(resolved_graph)
    resolved_id = review_id if review_id else uuid.uuid4().hex
    config = {"configurable": {"thread_id": resolved_id}}
    resolved_graph.invoke(
        {
            "review_id": resolved_id,
            "paper_text": paper_text,
            "sections": [],
            "confirmed": False,
            "status": STATUS_DRAFTING,
            "score_node_calls": 0,
            "parse_node_calls": 0,
            "retrieve_node_calls": 0,
        },
        config=config,
    )
    return resolved_id


def resume_review(review_id: str, sections: Any, *, graph: Any = None) -> dict[str, Any]:
    """用 Command(resume={"sections": [...]}) 继续评审，返回最终状态。

    已完成的评审单直接返回当前状态，不重复推进，评分节点调用次数不增加。
    """
    resolved_graph = graph if graph is not None else _default_graph()
    _require_checkpointer(resolved_graph)
    config = {"configurable": {"thread_id": review_id}}
    snapshot = resolved_graph.get_state(config)
    if not snapshot.values:
        raise ValueError(f"找不到评审单 {review_id} 的检查点，无法继续")
    if not snapshot.next:
        return dict(snapshot.values)
    final = resolved_graph.invoke(Command(resume={"sections": list(sections)}), config=config)
    return dict(final)
