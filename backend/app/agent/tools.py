"""Injected, deterministic tool registry for the LangChain agent layer."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from backend.app.scoring.selection import (
    apply_mention_guard,
    join_evidence,
    quote_is_substring,
)

ERROR_CODES = {
    "param_invalid",
    "not_found",
    "not_allowed",
    "quote_not_substring",
    "budget_exceeded",
}
BANDS = ("充分", "基本", "不足", "证据不足")


@dataclass
class ToolContext:
    review_id: str = ""
    contest_id: str = ""
    rubric_id: str = ""
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    retrieve_fn: Callable[..., Any] | None = None
    read_parent_fn: Callable[[str], str | None] | None = None
    findings_fn: Callable[[], list[dict[str, Any]]] | None = None
    results: dict[str, Any] = field(default_factory=dict)
    retrieved: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    submitted: set[str] = field(default_factory=set)


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error_code": None, "message": None}


def _error(code: str, message: str) -> dict[str, Any]:
    if code not in ERROR_CODES:
        raise ValueError(f"unsupported tool error code: {code}")
    return {"ok": False, "data": None, "error_code": code, "message": message}


def _args_dict(args: Any) -> dict[str, Any] | None:
    return dict(args) if isinstance(args, Mapping) else None


def _required_string(args: dict[str, Any], name: str) -> tuple[str | None, dict[str, Any] | None]:
    value = args.get(name)
    if not isinstance(value, str) or not value.strip():
        return None, _error("param_invalid", f"参数 {name} 必须是非空字符串")
    return value, None


def _dimension(ctx: ToolContext, code: str) -> dict[str, Any] | None:
    return next(
        (item for item in ctx.dimensions if isinstance(item, Mapping) and item.get("dimension_code") == code),
        None,
    )


def _parent_dict(parent: Any) -> dict[str, Any]:
    if isinstance(parent, Mapping):
        get = parent.get
    else:
        get = lambda key, default=None: getattr(parent, key, default)
    return {
        "parent_id": str(get("parent_id", "")),
        "section_type": str(get("section_type", "")),
        "chunk_ids": tuple(str(item) for item in (get("chunk_ids", ()) or ())),
        "content": str(get("content", "")),
        "review_id": str(get("review_id", "")),
    }


def list_dimensions(ctx: ToolContext) -> dict[str, Any]:
    if not ctx.dimensions:
        return _error("not_allowed", "当前评审未绑定赛题量规")
    fields = ("dimension_code", "name", "weight", "section_types", "evidence_prompts")
    return _ok({"dimensions": [{key: item.get(key) for key in fields} for item in ctx.dimensions]})


def search_evidence(
    ctx: ToolContext,
    dimension_code: str,
    query: str = "",
    section_types: list[str] | None = None,
) -> dict[str, Any]:
    dimension = _dimension(ctx, dimension_code)
    if dimension is None:
        return _error("param_invalid", f"未知 dimension_code: {dimension_code}")
    if ctx.retrieve_fn is None:
        return _error("not_allowed", "当前未注入 retrieve_fn")
    if not isinstance(query, str) or not isinstance(section_types, (list, type(None))):
        return _error("param_invalid", "query 必须是字符串，section_types 必须是字符串数组或 null")
    if section_types is not None and not all(isinstance(item, str) for item in section_types):
        return _error("param_invalid", "section_types 必须是字符串数组")
    types = tuple(section_types) if section_types is not None else tuple(dimension.get("section_types") or ())
    result = ctx.retrieve_fn(
        query,
        contest_id=ctx.contest_id,
        rubric_id=ctx.rubric_id,
        review_id=ctx.review_id,
        dimension_code=dimension_code,
        section_types=types,
    )
    parents = tuple(_parent_dict(parent) for parent in (getattr(result, "parents", ()) or ()))
    if getattr(result, "status", None) == "证据不足" or not parents:
        return _ok([])
    cache = ctx.retrieved.setdefault(dimension_code, {})
    for parent in parents:
        existing = cache.get(parent["parent_id"])
        if existing is not None:
            merged = tuple(dict.fromkeys((*existing["chunk_ids"], *parent["chunk_ids"])))
            parent = {**existing, **parent, "chunk_ids": merged}
        cache[parent["parent_id"]] = parent
    return _ok([
        {
            "parent_id": parent["parent_id"],
            "section_type": parent["section_type"],
            "chunk_ids": parent["chunk_ids"],
            "excerpt": parent["content"][:200],
        }
        for parent in cache.values()
    ])


def read_parent(ctx: ToolContext, parent_id: str) -> dict[str, Any]:
    if not isinstance(parent_id, str) or not parent_id.strip():
        return _error("param_invalid", "参数 parent_id 必须是非空字符串")
    parent = next(
        (item for by_id in ctx.retrieved.values() for item in by_id.values() if item["parent_id"] == parent_id),
        None,
    )
    if parent is None:
        return _error("not_found", f"parent_id 未在本次检索结果中: {parent_id}")
    if ctx.read_parent_fn is None:
        return _error("not_allowed", "当前未注入 read_parent_fn")
    content = ctx.read_parent_fn(parent_id)
    if content is None:
        return _error("not_found", f"找不到父块: {parent_id}")
    text = str(content)
    data: dict[str, Any] = {
        "parent_id": parent_id,
        "section_type": parent["section_type"],
        "content": text[:4000],
    }
    if len(text) > 4000:
        data["truncated"] = True
    return _ok(data)


def check_consistency(ctx: ToolContext, kinds: list[str] | None = None) -> dict[str, Any]:
    if kinds is not None and (not isinstance(kinds, list) or not all(isinstance(item, str) for item in kinds)):
        return _error("param_invalid", "kinds 必须是字符串数组或 null")
    if ctx.findings_fn is None:
        return _error("not_allowed", "当前未注入 findings_fn")
    findings = list(ctx.findings_fn() or [])
    if kinds:
        allowed = set(kinds)
        findings = [item for item in findings if isinstance(item, Mapping) and item.get("kind") in allowed]
    return _ok({"findings": findings, "count": len(findings)})


def get_constraints(ctx: ToolContext) -> dict[str, Any]:
    if not ctx.constraints:
        return _error("not_allowed", "当前评审没有可用约束")
    fields = ("name", "check_type", "params", "section_types")
    return _ok([{key: item.get(key) for key in fields} for item in ctx.constraints])


def submit_dimension(
    ctx: ToolContext,
    dimension_code: str,
    band: str,
    chunk_id: str,
    quote: str,
) -> dict[str, Any]:
    dimension = _dimension(ctx, dimension_code)
    if dimension is None:
        return _error("param_invalid", f"未知 dimension_code: {dimension_code}")
    if band not in BANDS:
        return _error("param_invalid", f"band 只能是 {'、'.join(BANDS)}")
    if any(not isinstance(value, str) or not value.strip() for value in (chunk_id, quote)):
        return _error("param_invalid", "chunk_id 与 quote 必须是非空字符串")
    if dimension_code in ctx.submitted:
        return _error("not_allowed", f"维度 {dimension_code} 已提交，拒绝覆盖")
    parents = list(ctx.retrieved.get(dimension_code, {}).values())
    if not quote_is_substring(quote, parents):
        return _error("quote_not_substring", "quote 必须是已检索父块中的连续子串")
    if band == "证据不足":
        final_band = band
        guard = {"band": band, "downgraded": False, "reasons": [], "checked": 0, "skipped": []}
        result = {"band": final_band, "status": final_band, "chunk_ids": [], "quote": None}
        data = {"dimension_code": dimension_code, "band": final_band, "downgraded": False}
    else:
        guard = apply_mention_guard(
            band,
            evidence_text=join_evidence(parents),
            constraints=ctx.constraints,
            dimension_section_types=dimension.get("section_types") or (),
            review_id=ctx.review_id,
            dimension_code=dimension_code,
        )
        final_band = guard["band"]
        result = {
            "band": final_band,
            "status": final_band,
            "chunk_ids": [chunk_id],
            "quote": quote,
            "guard": guard,
        }
        data = {"dimension_code": dimension_code, "band": final_band, "downgraded": bool(guard["downgraded"])}
    ctx.results[dimension_code] = result
    ctx.submitted.add(dimension_code)
    return _ok(data)


def call_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(name, str) or name not in {
        "list_dimensions", "search_evidence", "read_parent", "check_consistency", "get_constraints", "submit_dimension"
    }:
        return _error("param_invalid", f"未知工具 {name}")
    parsed = _args_dict(args)
    if parsed is None:
        return _error("param_invalid", "工具参数必须是对象")
    try:
        if name == "list_dimensions":
            if parsed:
                return _error("param_invalid", "list_dimensions 不接受参数")
            return list_dimensions(ctx)
        if name == "search_evidence":
            code, error = _required_string(parsed, "dimension_code")
            if error:
                return error
            query = parsed.get("query", "")
            types = parsed.get("section_types")
            if not isinstance(query, str) or (types is not None and (not isinstance(types, list) or not all(isinstance(x, str) for x in types))):
                return _error("param_invalid", "search_evidence 参数类型错误")
            return search_evidence(ctx, code, query, types)
        if name == "read_parent":
            parent_id, error = _required_string(parsed, "parent_id")
            return error or read_parent(ctx, parent_id)
        if name == "check_consistency":
            kinds = parsed.get("kinds")
            if kinds is not None and (not isinstance(kinds, list) or not all(isinstance(x, str) for x in kinds)):
                return _error("param_invalid", "kinds 参数类型错误")
            return check_consistency(ctx, kinds)
        if name == "get_constraints":
            if parsed:
                return _error("param_invalid", "get_constraints 不接受参数")
            return get_constraints(ctx)
        required = {}
        for key in ("dimension_code", "band", "chunk_id", "quote"):
            value, error = _required_string(parsed, key)
            if error:
                return error
            required[key] = value
        return submit_dimension(ctx, **required)
    except (TypeError, ValueError) as exc:
        return _error("param_invalid", str(exc))


class _EmptyArgs(BaseModel):
    """No arguments."""


class _SearchArgs(BaseModel):
    dimension_code: str = Field(description="量规维度代码")
    query: str = Field(default="", description="检索问题")
    section_types: list[str] | None = Field(default=None, description="可选章节类型")


class _ParentArgs(BaseModel):
    parent_id: str = Field(description="已检索父块 ID")


class _ConsistencyArgs(BaseModel):
    kinds: list[str] | None = Field(default=None, description="可选 finding 类型")


class _SubmitArgs(BaseModel):
    dimension_code: str = Field(description="量规维度代码")
    # 用 Literal 而不是纯 description：description 只是提示，模型自创 high/medium
    # 这类英文档位时校验仍会通过；Literal 会在工具 schema 层生成 enum 约束。
    band: Literal["充分", "基本", "不足", "证据不足"] = Field(description="档位")
    chunk_id: str = Field(description="引用切片 ID")
    quote: str = Field(description="父块中的连续原句")


def _json_result(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)


def build_tools(ctx: ToolContext) -> list[BaseTool]:
    def list_dimensions_tool() -> str:
        return _json_result(call_tool(ctx, "list_dimensions", {}))

    def search_evidence_tool(dimension_code: str, query: str = "", section_types: list[str] | None = None) -> str:
        return _json_result(call_tool(ctx, "search_evidence", {"dimension_code": dimension_code, "query": query, "section_types": section_types}))

    def read_parent_tool(parent_id: str) -> str:
        return _json_result(call_tool(ctx, "read_parent", {"parent_id": parent_id}))

    def check_consistency_tool(kinds: list[str] | None = None) -> str:
        return _json_result(call_tool(ctx, "check_consistency", {"kinds": kinds}))

    def get_constraints_tool() -> str:
        return _json_result(call_tool(ctx, "get_constraints", {}))

    def submit_dimension_tool(dimension_code: str, band: str, chunk_id: str, quote: str) -> str:
        return _json_result(call_tool(ctx, "submit_dimension", {"dimension_code": dimension_code, "band": band, "chunk_id": chunk_id, "quote": quote}))

    return [
        StructuredTool.from_function(list_dimensions_tool, name="list_dimensions", description="读取本次评审绑定量规的全部维度。", args_schema=_EmptyArgs),
        StructuredTool.from_function(search_evidence_tool, name="search_evidence", description="按维度检索证据父块，返回短摘要。", args_schema=_SearchArgs),
        StructuredTool.from_function(read_parent_tool, name="read_parent", description="读取本次检索白名单内的父块全文。", args_schema=_ParentArgs),
        StructuredTool.from_function(check_consistency_tool, name="check_consistency", description="检查已注入的数字、引用与范围一致性问题。", args_schema=_ConsistencyArgs),
        StructuredTool.from_function(get_constraints_tool, name="get_constraints", description="读取本次评审的约束只读视图。", args_schema=_EmptyArgs),
        StructuredTool.from_function(submit_dimension_tool, name="submit_dimension", description="记录某一维的最终结论。这是唯一能记录结论的工具；不调用它，这一维在本系统里等于未评。band 只能取 充分 / 基本 / 不足 / 证据不足；quote 必须逐字取自 read_parent 读到的父块全文，不得取自 search_evidence 的摘要。证据不足时 band 传「证据不足」、quote 传空字符串。", args_schema=_SubmitArgs),
    ]
