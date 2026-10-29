from types import SimpleNamespace

from backend.app.agent.context import build_context
from backend.app.agent.critique import critique
from backend.app.scoring.aggregate import BANDS, weighted_sum


def _ctx(contents=("evidence",), constraints=None):
    dims = [
        {"dimension_code": f"D{i}", "name": f"d{i}", "weight": i * 10, "section_types": ["模型"]}
        for i in range(1, 6)
    ]
    ctx = build_context(
        review_id="r", contest_id="c", rubric_id="rb", dimensions=dims,
        constraints=constraints or [], retrieve_fn=lambda *a, **k: SimpleNamespace(status="证据不足", parents=[]),
        read_parent_fn=lambda _: None, findings_fn=lambda: [],
    )
    for dim in dims:
        ctx.retrieved[dim["dimension_code"]] = {
            f"p-{dim['dimension_code']}": {"parent_id": f"p-{dim['dimension_code']}", "chunk_ids": (f"ch-{dim['dimension_code']}",), "content": contents[0], "section_type": "模型"}
        }
    return ctx


def test_mention_guard_downgrades_sufficient():
    ctx = _ctx(constraints=[{"name": "必须提及", "check_type": "mention", "params": {"keywords": ["缺失词"]}, "section_types": []}])
    result, actions = critique(ctx, {"D1": {"band": BANDS[0], "status": BANDS[0]}})
    assert result["D1"]["band"] == BANDS[1]
    assert any(a["action"] == "downgrade" and a["result_note"] == "mention_guard" for a in actions)


def test_model_valid_downgrade():
    ctx = _ctx()
    def chat(*args, **kwargs):
        return {"content": '{"downgrade":true,"reason":"weak","chunk_id":"ch-D1","quote":"evidence"}', "tool_calls": []}
    result, actions = critique(ctx, {"D1": {"band": BANDS[1], "status": BANDS[1]}}, chat_fn=chat)
    assert result["D1"]["band"] == BANDS[2]
    assert actions[-1]["action"] == "downgrade"


def test_upgrade_is_rejected():
    ctx = _ctx()
    result, actions = critique(ctx, {"D1": {"band": BANDS[1], "status": BANDS[1]}}, chat_fn=lambda *a, **k: {"content": '{"downgrade":false,"band":"充分"}'})
    assert result["D1"]["band"] == BANDS[1]
    assert actions[-1]["result_note"] == "upgrade_not_allowed"


def test_non_substring_is_rejected():
    ctx = _ctx()
    result, actions = critique(ctx, {"D1": {"band": BANDS[1], "status": BANDS[1]}}, chat_fn=lambda *a, **k: {"content": '{"downgrade":true,"chunk_id":"ch-D1","quote":"other"}'})
    assert result["D1"]["band"] == BANDS[1]
    assert actions[-1]["result_note"] == "quote_not_substring"


def test_two_step_downgrade_is_rejected():
    ctx = _ctx()
    result, actions = critique(ctx, {"D1": {"band": BANDS[0], "status": BANDS[0]}}, chat_fn=lambda *a, **k: {"content": '{"downgrade":true,"band":"不足","chunk_id":"ch-D1","quote":"evidence"}'})
    assert result["D1"]["band"] == BANDS[0]
    assert actions[-1]["result_note"] == "downgrade_step_invalid"


def test_downgrade_quota_is_global():
    ctx = _ctx(constraints=[{"name": "必须提及", "check_type": "mention", "params": {"keywords": ["缺失词"]}, "section_types": []}])
    initial = {f"D{i}": {"band": BANDS[0], "status": BANDS[0]} for i in range(1, 4)}
    result, actions = critique(ctx, initial)
    assert [result[f"D{i}"]["band"] for i in range(1, 3)] == [BANDS[1], BANDS[1]]
    assert result["D3"]["band"] == BANDS[0]
    assert actions[-1]["result_note"] == "quota_exceeded"


def test_weighted_sum_reflects_downgrade():
    ctx = _ctx(constraints=[{"name": "必须提及", "check_type": "mention", "params": {"keywords": ["缺失词"]}, "section_types": []}])
    before = {"D1": {"dimension_code": "D1", "band": BANDS[0], "status": BANDS[0]}, "D2": {"dimension_code": "D2", "band": BANDS[0], "status": BANDS[0]}}
    after, _ = critique(ctx, before)
    recalculated = weighted_sum(ctx.dimensions, list(after.values()))
    assert recalculated["weighted"][0]["band"] == BANDS[1]


def test_no_eligible_results_are_unchanged():
    ctx = _ctx()
    result, actions = critique(ctx, {"D1": {"band": BANDS[3], "status": BANDS[3]}})
    assert result == {"D1": {"band": BANDS[3], "status": BANDS[3]}}
    assert actions == []
