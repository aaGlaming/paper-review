from backend.app.chat import records


def _review(review_id="a" * 32):
    return {
        "review_id": review_id,
        "contest_id": "c1",
        "rubric_id": "rubric-1",
        "created_at": "2026-01-02T03:04:05",
        "dimensions": [
            {"dimension_code": f"dim{i}", "band": "充分", "quote": f"原句{i}"}
            for i in range(5)
        ],
        "change_list": [{"kind": "修改", "target": "段落", "text": "建议"}],
    }


def test_load_record_blocks_builds_five_citable_parents_and_non_citable_overview(monkeypatch):
    monkeypatch.setattr(records.report_store, "load_review", lambda *a, **k: _review())
    blocks = records.load_record_blocks("a" * 32)
    assert len(blocks) == 6
    assert all(item["citable"] is True for item in blocks[:5])
    assert blocks[-1]["dimension_code"] == "record_summary"
    assert blocks[-1]["parent_id"] == f"rr-{'a' * 32}-overview"
    assert blocks[-1]["citable"] is False
    assert "[修改] 段落 → 建议" in blocks[-1]["content"]


def test_load_record_blocks_missing_review_returns_empty(monkeypatch):
    monkeypatch.setattr(records.report_store, "load_review", lambda *a, **k: None)
    assert records.load_record_blocks("missing") == []


def test_load_record_blocks_works_without_index_or_chroma(monkeypatch):
    monkeypatch.setattr(records.report_store, "load_review", lambda *a, **k: _review())
    monkeypatch.setattr(records.parent_child, "get_collection", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    assert len(records.load_record_blocks("a" * 32)) == 6
