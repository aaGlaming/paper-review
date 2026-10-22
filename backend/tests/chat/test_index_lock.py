import json
import os

import pytest

from scripts import index_review_records as script


def test_existing_live_lock_stops_main_flow_with_already_running_code(tmp_path, capsys):
    path = tmp_path / "index.lock"
    path.write_text(json.dumps({"pid": os.getpid(), "started_at": "test-start"}), encoding="utf-8")
    calls = []
    assert script.run_exclusively(lambda: calls.append(True) or 0, lock_path=path) == 2
    assert calls == []
    output = capsys.readouterr().out
    assert "另一个回填进程正在运行" in output
    assert f"pid={os.getpid()}" in output
    assert "test-start" in output


def test_deleted_lock_allows_flow_and_cleans_up_on_exception(tmp_path):
    path = tmp_path / "index.lock"
    path.write_text("old", encoding="utf-8")
    path.unlink()
    calls = []

    def action():
        owner = json.loads(path.read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()
        assert owner["started_at"]
        calls.append(True)
        return 0

    assert script.run_exclusively(action, lock_path=path) == 0
    assert calls == [True]
    assert not path.exists()

    def failed_action():
        raise RuntimeError("failed")

    with pytest.raises(RuntimeError, match="failed"):
        script.run_exclusively(failed_action, lock_path=path)
    assert not path.exists()


def test_backfill_skips_only_identical_parent_and_child_content(monkeypatch):
    review = {"review_id": "a" * 32, "contest_id": "c1", "rubric_id": "r1",
              "dimensions": [{"dimension_code": "assumption", "band": "基本", "quote": "原句"}]}
    parents, children = script.build_review_record(review, contest_id="c1", rubric_id="r1")

    class Collection:
        def count(self):
            return 1

        def get(self, **kwargs):
            return {"ids": [item.chunk_id for item in children],
                    "documents": [item.text for item in children],
                    "metadatas": [script.parent_child.child_metadata(item) for item in children]}

    collection = Collection()
    monkeypatch.setattr(script, "load_review", lambda *a, **k: review)
    monkeypatch.setattr(script.parent_child, "get_parents", lambda *a, **k: parents)
    monkeypatch.setattr(script, "get_collection", lambda *a, **k: collection)
    monkeypatch.setattr(script, "index_review_record",
                        lambda *a, **k: pytest.fail("identical records must not be rewritten"))
    assert script._run([review["review_id"]], client=None, dry_run=False) == 0
    review["dimensions"][0]["quote"] = "已修改的原句"
    assert not script._record_is_current(review["review_id"], collection)
