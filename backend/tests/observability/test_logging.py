import json
from datetime import datetime, timedelta

import pytest

from backend.app.observability import logging as observability_logging


def _enable(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_DISABLED", "")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    observability_logging.reset_logging_for_tests()


def test_all_modules_create_directories_and_invalid_module_rejected(tmp_path, monkeypatch):
    _enable(tmp_path, monkeypatch)
    observability_logging.setup_logging()
    for module in observability_logging.MODULES:
        assert (tmp_path / module).is_dir()
    with pytest.raises(ValueError):
        observability_logging.log_event("not_a_module", "bad")


def test_json_line_contains_required_fields_and_unicode(tmp_path, monkeypatch):
    _enable(tmp_path, monkeypatch)
    observability_logging.log_event("scoring", "dimension_scored", band="不足", review_id="r1")
    path = next((tmp_path / "scoring").glob("scoring-*.log"))
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert {"ts", "level", "module", "event"} <= row.keys()
    assert row["module"] == "scoring"
    assert row["band"] == "不足"
    assert datetime.fromisoformat(row["ts"]).tzinfo is not None


def test_disabled_does_not_create_directory_or_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_DISABLED", "1")
    observability_logging.reset_logging_for_tests()
    observability_logging.log_event("api", "request")
    assert not any(tmp_path.rglob("*"))


def test_secret_values_never_written(tmp_path, monkeypatch):
    _enable(tmp_path, monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "secret-key-value")
    observability_logging.log_event("llm", "llm_call", model="demo", ok=True)
    content = "\n".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.log"))
    assert "secret-key-value" not in content
    assert "LLM_API_KEY" not in content


def test_bound_review_id_is_backfilled_for_context_free_modules(tmp_path, monkeypatch):
    """llm 这类拿不到评审参数的模块，也要被自动串进同一次预审。

    2026-10-20 实测：未加 ContextVar 前 llm 日志 2244 条里 0 条带 review_id，
    scoring 也只有 67/1183，「用一条 review_id 串起全过程」这条判据直接不成立。
    """
    _enable(tmp_path, monkeypatch)
    token = observability_logging.bind_review_id("rid-auto")
    try:
        observability_logging.log_event("llm", "llm_call", op="chat", model="demo")
        observability_logging.log_event("scoring", "dimension_scored", review_id=None)
    finally:
        observability_logging.unbind_review_id(token)

    rows = [json.loads(p.read_text(encoding="utf-8").strip())
            for p in tmp_path.rglob("*.log") if p.stat().st_size]
    assert rows and all(row.get("review_id") == "rid-auto" for row in rows)

    # 解绑后不该再被回填
    observability_logging.log_event("llm", "llm_call", op="embed", model="demo")
    last = json.loads(
        (tmp_path / "llm").joinpath(max((tmp_path / "llm").glob("llm-*.log"))).read_text(
            encoding="utf-8").strip().splitlines()[-1])
    assert last.get("review_id") is None


def test_bound_review_id_does_not_override_explicit_field(tmp_path, monkeypatch):
    _enable(tmp_path, monkeypatch)
    token = observability_logging.bind_review_id("rid-ctx")
    try:
        observability_logging.log_event("api", "request", review_id="rid-explicit")
    finally:
        observability_logging.unbind_review_id(token)
    row = json.loads(next((tmp_path / "api").glob("api-*.log")).read_text(encoding="utf-8").strip())
    assert row["review_id"] == "rid-explicit"


def test_size_rollover_keeps_at_most_five_backups(tmp_path, monkeypatch):
    _enable(tmp_path, monkeypatch)
    observability_logging.set_max_bytes_for_tests(256)
    # 迭代次数压到刚好触发十余次滚动：本机沙箱的批量删除保护在累计 50 次
    # unlink 后会终止进程（[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]），
    # 80 条会产生 40 次以上滚动、删除次数越线，导致全量跑时该用例崩掉。
    # 断言（备份数量上限、是否出现 .1）不变，只缩小样本量。
    for index in range(24):
        observability_logging.log_event("api", "request", index=index, payload="x" * 80)
    files = list((tmp_path / "api").glob("api-*.log*"))
    assert len(files) <= 6
    assert any(path.name.endswith(".1") for path in files)
