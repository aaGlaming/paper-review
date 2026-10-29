from types import SimpleNamespace
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from backend.app.agent.middleware import BudgetExceeded, BudgetMiddleware, TraceMiddleware


def _runtime():
    return SimpleNamespace()


def _request(name="search_evidence", args=None, state=None):
    return SimpleNamespace(
        tool_call={"name": name, "args": args or {}, "id": "call-1"},
        state=state or {"review_id": "r1"},
    )


def test_model_budget_is_enforced():
    middleware = BudgetMiddleware(max_model_calls=1)
    middleware.before_model({"review_id": "r1"}, _runtime())
    with pytest.raises(BudgetExceeded) as exc:
        middleware.before_model({"review_id": "r1"}, _runtime())
    assert exc.value.reason == "model_calls"

def test_default_model_budget_allows_twelve_calls():
    assert BudgetMiddleware().max_model_calls == 12


def test_tool_budget_is_enforced():
    middleware = BudgetMiddleware(max_tool_calls=1)
    handler = lambda request: ToolMessage(content="{}", tool_call_id="call-1")
    middleware.wrap_tool_call(_request(), handler)
    with pytest.raises(BudgetExceeded) as exc:
        middleware.wrap_tool_call(_request(), handler)
    assert exc.value.reason == "tool_calls"


def test_dimension_step_budget_is_enforced():
    middleware = BudgetMiddleware(max_steps_per_dimension=3)
    handler = lambda request: ToolMessage(content="{}", tool_call_id="call-1")
    for _ in range(3):
        middleware.wrap_tool_call(_request(args={"dimension_code": "D1"}), handler)
    with pytest.raises(BudgetExceeded) as exc:
        middleware.wrap_tool_call(_request(args={"dimension_code": "D1"}), handler)
    assert exc.value.reason == "dimension_steps"


def test_wall_clock_budget_is_enforced():
    middleware = BudgetMiddleware(wall_clock_seconds=0)
    with pytest.raises(BudgetExceeded) as exc:
        middleware.before_model({"review_id": "r1"}, _runtime())
    assert exc.value.reason == "wall_clock"


def test_trace_after_model_records_tool_decision_without_original_text(monkeypatch):
    calls = []
    middleware = TraceMiddleware(recorder=lambda **kwargs: calls.append(kwargs))
    state = {"review_id": "r1", "messages": [AIMessage(content="论文原句不应进入摘要", tool_calls=[{"name": "list_dimensions", "args": {}, "id": "1"}])]}
    middleware.after_model(state, _runtime())
    assert calls[0]["node"] == "model"
    assert calls[0]["action"] == "list_dimensions"
    assert "论文原句" not in calls[0]["result"]["message"]


def test_trace_tool_failure_preserves_error(monkeypatch):
    calls = []
    monkeypatch.setattr("backend.app.agent.middleware.record_call", lambda **kwargs: calls.append(kwargs))
    middleware = TraceMiddleware()
    request = _request(state={"review_id": "r1"})
    response = middleware.wrap_tool_call(request, lambda _: ToolMessage(content='{"ok":false,"error_code":"not_found"}', tool_call_id="call-1"))
    assert response.content
    assert calls[0]["result"]["ok"] is False
    assert calls[0]["result"]["error_code"] == "not_found"

def _result(data):
    return ToolMessage(content=json.dumps({"ok": True, "data": data, "error_code": None}), tool_call_id="call-1")

def test_no_progress_after_two_empty_evidence_calls():
    middleware = BudgetMiddleware()
    handler = lambda _: _result([])
    middleware.wrap_tool_call(_request("search_evidence"), handler)
    with pytest.raises(BudgetExceeded) as exc:
        middleware.wrap_tool_call(_request("search_evidence"), handler)
    assert exc.value.reason == "no_progress"

def test_new_evidence_resets_no_progress_streak():
    middleware = BudgetMiddleware()
    middleware.wrap_tool_call(_request("search_evidence"), lambda _: _result([{"parent_id": "p1"}]))
    middleware.wrap_tool_call(_request("search_evidence"), lambda _: _result([]))
    middleware.wrap_tool_call(_request("search_evidence"), lambda _: _result([{"parent_id": "p2"}]))
    assert middleware.no_progress_streak == 0

def test_read_parent_does_not_change_no_progress_streak():
    middleware = BudgetMiddleware()
    middleware.wrap_tool_call(_request("search_evidence"), lambda _: _result([]))
    middleware.wrap_tool_call(_request("read_parent"), lambda _: _result({"content": "x"}))
    with pytest.raises(BudgetExceeded) as exc:
        middleware.wrap_tool_call(_request("search_evidence"), lambda _: _result([]))
    assert exc.value.reason == "no_progress"
