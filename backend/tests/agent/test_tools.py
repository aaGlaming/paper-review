from types import SimpleNamespace

import pytest

from backend.app.agent.tools import ToolContext, build_tools, call_tool


def make_context(*, empty_dimensions=False, empty_constraints=False):
    parents = (
        SimpleNamespace(
            parent_id="parent-1",
            section_type="method",
            chunk_ids=("chunk-1",),
            content="板凳宽度为 42 厘米，实验使用三组数据。",
            review_id="review-1",
        ),
        SimpleNamespace(
            parent_id="parent-2",
            section_type="result",
            chunk_ids=("chunk-2",),
            content="结果显示误差低于 5%，并记录了复现实验。",
            review_id="review-1",
        ),
    )
    dimensions = [] if empty_dimensions else [
        {
            "dimension_code": f"D{i}",
            "name": f"维度 {i}",
            "weight": i / 10,
            "section_types": ["method", "result"],
            "evidence_prompts": ["给出证据"],
        }
        for i in range(1, 6)
    ]
    constraints = [] if empty_constraints else [
        {
            "name": "必须提到关键词",
            "check_type": "mention",
            "params": {"keywords": ["不存在的关键词"]},
            "section_types": ["method"],
        },
        {
            "name": "宽度范围",
            "check_type": "numeric_range",
            "params": {"min": 1, "max": 100},
            "section_types": ["method"],
        },
    ]

    def retrieve(query, **kwargs):
        return SimpleNamespace(status="命中", parents=parents)

    def read_parent(parent_id):
        return next((p.content for p in parents if p.parent_id == parent_id), None)

    def findings():
        return [
            {"kind": "number", "message": "412 与 386 冲突"},
            {"kind": "citation", "message": "引用缺页码"},
        ]

    return ToolContext(
        review_id="review-1",
        contest_id="contest-1",
        rubric_id="rubric-1",
        dimensions=dimensions,
        constraints=constraints,
        retrieve_fn=retrieve,
        read_parent_fn=read_parent,
        findings_fn=findings,
    )


def test_list_dimensions_returns_rubric_fields():
    result = call_tool(make_context(), "list_dimensions", {})
    assert result["ok"] is True
    assert len(result["data"]["dimensions"]) == 5
    assert {"weight", "section_types"} <= set(result["data"]["dimensions"][0])


def test_list_dimensions_without_contest_is_not_allowed():
    result = call_tool(make_context(empty_dimensions=True), "list_dimensions", {})
    assert result["ok"] is False
    assert result["error_code"] == "not_allowed"


def test_search_evidence_returns_short_parent_summaries():
    ctx = make_context()
    result = call_tool(ctx, "search_evidence", {"dimension_code": "D1", "query": "宽度"})
    assert result["ok"] is True
    assert len(result["data"]) == 2
    assert all(len(item["excerpt"]) <= 200 for item in result["data"])
    assert "板凳宽度为 42 厘米，实验使用三组数据。" not in result["data"][0]["excerpt"] or len(result["data"][0]["excerpt"]) < 200
    assert "parent-1" in ctx.retrieved["D1"]


def test_search_evidence_empty_is_ok():
    ctx = make_context()
    ctx.retrieve_fn = lambda query, **kwargs: SimpleNamespace(status="证据不足", parents=())
    result = call_tool(ctx, "search_evidence", {"dimension_code": "D1"})
    assert result == {"ok": True, "data": [], "error_code": None, "message": None}


def test_search_evidence_unknown_dimension_is_param_invalid():
    result = call_tool(make_context(), "search_evidence", {"dimension_code": "DX"})
    assert result["error_code"] == "param_invalid"


def test_read_parent_only_reads_retrieved_parent():
    ctx = make_context()
    call_tool(ctx, "search_evidence", {"dimension_code": "D1"})
    found = call_tool(ctx, "read_parent", {"parent_id": "parent-1"})
    missing = call_tool(ctx, "read_parent", {"parent_id": "parent-x"})
    assert found["ok"] is True and found["data"]["parent_id"] == "parent-1"
    assert missing["ok"] is False and missing["error_code"] == "not_found"


def test_read_parent_truncates_long_content():
    ctx = make_context()
    ctx.read_parent_fn = lambda parent_id: "x" * 5001
    call_tool(ctx, "search_evidence", {"dimension_code": "D1"})
    result = call_tool(ctx, "read_parent", {"parent_id": "parent-1"})
    assert result["data"]["truncated"] is True
    assert len(result["data"]["content"]) == 4000


def test_check_consistency_filters_kinds():
    result = call_tool(make_context(), "check_consistency", {"kinds": ["number"]})
    assert result["ok"] is True
    assert result["data"]["count"] == 1
    assert result["data"]["findings"][0]["kind"] == "number"


def test_get_constraints_returns_safe_view_and_rejects_empty():
    result = call_tool(make_context(), "get_constraints", {})
    assert result["ok"] is True
    assert len(result["data"]) == 2
    assert set(result["data"][0]) == {"name", "check_type", "params", "section_types"}
    empty = call_tool(make_context(empty_constraints=True), "get_constraints", {})
    assert empty["error_code"] == "not_allowed"


def test_submit_dimension_writes_valid_result():
    ctx = make_context()
    call_tool(ctx, "search_evidence", {"dimension_code": "D1"})
    result = call_tool(ctx, "submit_dimension", {
        "dimension_code": "D1", "band": "基本", "chunk_id": "chunk-1", "quote": "板凳宽度为 42 厘米",
    })
    assert result["ok"] is True
    assert ctx.results["D1"]["band"] == "基本"
    assert ctx.results["D1"]["quote"] == "板凳宽度为 42 厘米"


def test_submit_dimension_rejects_non_substring_without_write():
    ctx = make_context()
    call_tool(ctx, "search_evidence", {"dimension_code": "D1"})
    result = call_tool(ctx, "submit_dimension", {
        "dimension_code": "D1", "band": "基本", "chunk_id": "chunk-1", "quote": "不存在的原句",
    })
    assert result["error_code"] == "quote_not_substring"
    assert "D1" not in ctx.results


def test_submit_dimension_applies_mention_guard():
    ctx = make_context()
    call_tool(ctx, "search_evidence", {"dimension_code": "D1"})
    result = call_tool(ctx, "submit_dimension", {
        "dimension_code": "D1", "band": "充分", "chunk_id": "chunk-1", "quote": "板凳宽度为 42 厘米",
    })
    assert result["data"]["band"] == "基本"
    assert result["data"]["downgraded"] is True
    assert ctx.results["D1"]["guard"]["downgraded"] is True


def test_submit_dimension_rejects_duplicate_without_overwrite():
    ctx = make_context()
    call_tool(ctx, "search_evidence", {"dimension_code": "D1"})
    args = {"dimension_code": "D1", "band": "基本", "chunk_id": "chunk-1", "quote": "板凳宽度为 42 厘米"}
    first = call_tool(ctx, "submit_dimension", args)
    second = call_tool(ctx, "submit_dimension", {**args, "band": "充分"})
    assert first["ok"] is True
    assert second["error_code"] == "not_allowed"
    assert ctx.results["D1"]["band"] == "基本"


def test_build_tools_returns_six_named_structured_tools():
    tools = build_tools(make_context())
    assert len(tools) == 6
    assert len({tool.name for tool in tools}) == 6
    assert all(tool.description and tool.args_schema for tool in tools)


def test_call_tool_invalid_name_missing_arg_and_invalid_band():
    ctx = make_context()
    unknown = call_tool(ctx, "not_a_tool", {})
    missing = call_tool(ctx, "search_evidence", {})
    invalid_band = call_tool(ctx, "submit_dimension", {
        "dimension_code": "D1", "band": "优秀", "chunk_id": "chunk-1", "quote": "x",
    })
    assert unknown["error_code"] == "param_invalid"
    assert missing["error_code"] == "param_invalid"
    assert invalid_band["error_code"] == "param_invalid"
