from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.agent import trace


def db_session():
    engine = create_engine("sqlite:///:memory:")
    trace.create_agent_trace_schema(engine)
    trace.create_agent_trace_schema(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_create_schema_is_idempotent():
    session = db_session()
    assert trace.AgentStep.__tablename__ == "agent_step"
    session.close()


def test_append_steps_are_numbered_and_loaded_in_order():
    session = db_session()
    first = trace.append_step(review_id="r1", node="tools", action="list_dimensions", args_digest="a", result_note="ok", ok=True, session=session)
    second = trace.append_step(review_id="r1", node="tools", action="get_constraints", args_digest="b", result_note="ok", ok=True, session=session)
    session.commit()
    assert [first["idx"], second["idx"]] == [1, 2]
    assert [item["action"] for item in trace.load_steps("r1", session=session)] == ["list_dimensions", "get_constraints"]


def test_different_reviews_have_independent_indexes():
    session = db_session()
    one = trace.append_step(review_id="r1", node="tools", action="a", args_digest="a", result_note="ok", ok=True, session=session)
    other = trace.append_step(review_id="r2", node="tools", action="b", args_digest="b", result_note="ok", ok=True, session=session)
    assert one["idx"] == other["idx"] == 1


def test_digest_args_is_stable_distinct_and_does_not_include_original_text():
    left = trace.digest_args({"quote": "论文原文", "n": 1})
    same = trace.digest_args({"n": 1, "quote": "论文原文"})
    right = trace.digest_args({"quote": "另一段", "n": 1})
    assert left == same
    assert left != right
    assert len(left) == 8
    assert "论文原文" not in left


def test_record_call_builds_success_and_failure_notes():
    session = db_session()
    success = trace.record_call(review_id="r1", action="search_evidence", args={"q": "x"}, result={"ok": True, "data": [1, 2]}, elapsed_ms=3, session=session)
    failure = trace.record_call(review_id="r1", action="read_parent", args={}, result={"ok": False, "error_code": "not_found", "message": "missing"}, elapsed_ms=4, session=session)
    assert success["result_note"] == "命中 2 条"
    assert "not_found" in failure["result_note"]


def test_record_note_is_bounded():
    session = db_session()
    result = trace.record_call(review_id="r1", action="x", args={}, result={"ok": False, "error_code": "param_invalid", "message": "x" * 500}, elapsed_ms=1, session=session)
    assert len(result["result_note"]) <= 256
