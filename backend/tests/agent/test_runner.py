from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from backend.app.agent.context import build_context
from backend.app.agent.runner import make_agent_runner
from backend.app.agent.tools import ToolContext
from backend.app.agent.tools import BANDS
import backend.app.agent.runner as runner_module
from backend.app.agent.middleware import BudgetExceeded
from langgraph.errors import GraphRecursionError


def _ctx():
    dimensions = [{"dimension_code": f"D{i}", "name": f"缁村害{i}", "weight": 20, "section_types": [], "evidence_prompts": []} for i in range(1, 6)]
    ctx = build_context(review_id="r1", contest_id="c1", rubric_id="rb1", dimensions=dimensions, constraints=[], retrieve_fn=lambda *a, **k: SimpleNamespace(status="璇佹嵁涓嶈冻", parents=[]), read_parent_fn=lambda _: None, findings_fn=lambda: [])
    for item in dimensions:
        ctx.retrieved[item["dimension_code"]] = {"p": {"parent_id": "p", "section_type": "", "chunk_ids": ("x",), "content": "x", "review_id": "r1"}}
    return ctx


def _chat_script(submit_count=5, error=None):
    calls = {"n": 0}
    def chat(messages, *, tools, temperature):
        calls["n"] += 1
        if error:
            raise error
        if calls["n"] <= submit_count:
            code = f"D{calls['n']}"
            return {"content": "", "tool_calls": [{"id": str(calls["n"]), "name": "submit_dimension", "arguments": {"dimension_code": code, "band": BANDS[-1], "chunk_id": "x", "quote": "x"}}], "finish_reason": "tool_calls"}
        return {"content": "瀹屾垚", "tool_calls": [], "finish_reason": "stop"}
    return chat


def test_runner_submits_all_dimensions():
    ctx = _ctx()
    result = make_agent_runner(ctx=ctx, chat_fn=_chat_script())({"review_id": "r1", "contest_id": "c1", "rubric_id": "rb1"})
    assert set(result["dimension_results"]) == {f"D{i}" for i in range(1, 6)}
    assert result["terminated_by"] == "all_submitted"


def test_runner_fills_missing_dimensions():
    ctx = _ctx()
    result = make_agent_runner(ctx=ctx, chat_fn=_chat_script(submit_count=2))({"review_id": "r1", "contest_id": "c1", "rubric_id": "rb1"})
    assert len(result["dimension_results"]) == 5
    assert "reason" in result["dimension_results"]["D5"]


def test_runner_budget_exhaustion_is_returned():
    ctx = _ctx()
    result = make_agent_runner(ctx=ctx, chat_fn=_chat_script(submit_count=5), budget={"max_model_calls": 1})({"review_id": "r1", "contest_id": "c1", "rubric_id": "rb1"})
    assert result["terminated_by"] == "budget_exhausted"


def test_runner_non_budget_error_is_raised():
    ctx = _ctx()
    error = RuntimeError("LLMResponseError")
    with pytest.raises(RuntimeError, match="LLMResponseError"):
        make_agent_runner(ctx=ctx, chat_fn=_chat_script(error=error))({"review_id": "r1", "contest_id": "c1", "rubric_id": "rb1"})

def test_runner_maps_no_progress_and_fills_missing(monkeypatch):
    class Graph:
        def invoke(self, *args, **kwargs):
            raise BudgetExceeded("no_progress")
    monkeypatch.setattr(runner_module, "build_review_agent", lambda *args, **kwargs: Graph())
    result = make_agent_runner(ctx=_ctx(), chat_fn=lambda *a, **k: None)({"review_id": "r1"})
    assert result["terminated_by"] == "no_progress"
    assert result["dimension_results"]["D1"]["status"] == result["dimension_results"]["D1"]["band"]

def test_runner_force_submit_validates_and_records_missing(monkeypatch):
    class Graph:
        def invoke(self, *args, **kwargs):
            return {}
    monkeypatch.setattr(runner_module, "build_review_agent", lambda *args, **kwargs: Graph())
    calls = []
    def force_chat(messages, *, tools, temperature):
        calls.append(messages)
        return {"content": '[{"dimension_code":"D1","band":"不足","quote":"x","chunk_id":"x"}]', "tool_calls": []}
    ctx = _ctx()
    result = make_agent_runner(ctx=ctx, chat_fn=force_chat)({"review_id": "r1"})
    assert result["dimension_results"]["D1"]["band"] == BANDS[2]
    assert calls

def test_runner_distinguishes_recursion_limit(monkeypatch):
    seen = {}
    class Graph:
        def invoke(self, *args, **kwargs):
            seen["limit"] = kwargs["config"]["recursion_limit"]
            raise GraphRecursionError("limit")
    monkeypatch.setattr(runner_module, "build_review_agent", lambda *args, **kwargs: Graph())
    result = make_agent_runner(ctx=_ctx(), chat_fn=lambda *a, **k: {"content":"", "tool_calls":[]})( {"review_id":"r1"})
    assert seen["limit"] == 45
    assert result["terminated_by"] == "recursion_limit_reached"

def test_runner_budget_remains_distinct_from_recursion(monkeypatch):
    class Graph:
        def invoke(self, *args, **kwargs):
            raise BudgetExceeded("model_calls")
    monkeypatch.setattr(runner_module, "build_review_agent", lambda *args, **kwargs: Graph())
    result = make_agent_runner(ctx=_ctx(), chat_fn=lambda *a, **k: None, budget={"max_model_calls": 1})( {"review_id":"r1"})
    assert result["terminated_by"] == "budget_exhausted"

def test_runner_critique_failure_keeps_results(monkeypatch):
    class Graph:
        def invoke(self, *args, **kwargs):
            return {}
    monkeypatch.setattr(runner_module, "build_review_agent", lambda *args, **kwargs: Graph())
    monkeypatch.setattr(runner_module, "critique", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("critique")))
    ctx = _ctx()
    ctx.results["D1"] = {"band": BANDS[2], "status": BANDS[2], "chunk_ids": ["x"], "quote": "x"}
    result = make_agent_runner(ctx=ctx, chat_fn=lambda *a, **k: None)({"review_id": "r1"})
    assert result["dimension_results"]["D1"]["band"] == BANDS[2]

