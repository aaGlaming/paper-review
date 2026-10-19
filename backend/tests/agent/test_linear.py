from types import SimpleNamespace

import pytest

from backend.app.agent.context import build_context
from backend.app.agent.linear import run_linear_probe
from backend.app.agent.tools import ToolContext


def context(retrieve_fn=None):
    parents = (SimpleNamespace(parent_id="p1", section_type="method", chunk_ids=("c1",), content="evidence"),)
    return build_context(
        review_id="r1", contest_id="c1", rubric_id="rubric-1",
        dimensions=[{"dimension_code": "D1", "name": "方法", "section_types": ["method"]}],
        constraints=[], retrieve_fn=retrieve_fn or (lambda query, **kwargs: SimpleNamespace(status="命中", parents=parents)),
        read_parent_fn=lambda parent_id: "evidence", findings_fn=lambda: [],
    )


def test_linear_probe_records_three_steps_and_returns_hits():
    calls = []
    result = run_linear_probe(context(), recorder=lambda **kwargs: calls.append(kwargs) or kwargs["result"])
    assert result == {"steps": 3, "first_dimension_hits": 1}
    assert [call["action"] for call in calls] == ["list_dimensions", "get_constraints", "search_evidence"]


def test_linear_probe_catches_retrieve_failure_and_continues():
    calls = []
    def fail(query, **kwargs):
        raise RuntimeError("offline probe failure")
    result = run_linear_probe(context(fail), recorder=lambda **kwargs: calls.append(kwargs) or kwargs["result"])
    assert result["steps"] == 3
    assert calls[-1]["result"]["ok"] is False


def test_build_context_rejects_missing_dimensions():
    with pytest.raises(ValueError, match="dimensions"):
        build_context(review_id="r", contest_id="c", rubric_id="u", dimensions=[], constraints=[], retrieve_fn=lambda *a, **k: None, read_parent_fn=None, findings_fn=None)


def test_linear_probe_does_not_write_results():
    ctx = context()
    run_linear_probe(ctx, recorder=lambda **kwargs: kwargs["result"])
    assert ctx.results == {}
