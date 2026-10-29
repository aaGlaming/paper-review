import ast
import json
from pathlib import Path

from scripts import check_logs


TODAY = "20261021"
OLD_DAY = "20261018"


def _log_root(tmp_path: Path, *, day: str | None = OLD_DAY) -> Path:
    for module in check_logs.MODULES:
        directory = tmp_path / module
        directory.mkdir()
        if day is not None and module in check_logs.REQUIRED_WRITERS:
            payload = {
                "ts": "2026-10-18T12:00:00+08:00",
                "level": "INFO",
                "module": module,
                "event": "test",
            }
            (directory / f"{module}-{day}.log").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_writer_from_day_three_passes_when_today_has_no_log(tmp_path, capsys):
    root = _log_root(tmp_path)

    assert check_logs.main(["--root", str(root), "--date", TODAY, "--since-days", "7"]) == 0
    assert "[ok] 15 dirs, 8 writers, 0 issue (window=20261015..20261021)" in capsys.readouterr().out


def test_no_writer_files_in_window_fails_with_module_names(tmp_path, capsys):
    root = _log_root(tmp_path, day=None)

    assert check_logs.main(["--root", str(root), "--date", TODAY, "--since-days", "7"]) == 1
    output = capsys.readouterr().out
    assert "api 在最近 7 天无任何日志" in output
    assert "importing 在最近 7 天无任何日志" in output
    assert "[fail] 8 issues" in output


def test_empty_file_in_window_still_fails(tmp_path, capsys):
    root = _log_root(tmp_path)
    (root / "api" / f"api-{OLD_DAY}.log").write_text("", encoding="utf-8")

    assert check_logs.main(["--root", str(root), "--date", TODAY, "--since-days", "7"]) == 1
    output = capsys.readouterr().out
    assert "required writer empty: api" in output
    assert "[fail] 1 issues" in output


def test_strict_today_keeps_old_daily_requirement(tmp_path, capsys):
    root = _log_root(tmp_path)

    assert check_logs.main(["--root", str(root), "--date", TODAY, "--strict-today"]) == 1
    output = capsys.readouterr().out
    assert "api 在最近 1 天无任何日志" in output


def test_secret_in_window_still_fails_validation(tmp_path, capsys):
    root = _log_root(tmp_path)
    api_log = root / "api" / f"api-{OLD_DAY}.log"
    payload = {
        "ts": "2026-10-18T12:00:00+08:00",
        "level": "INFO",
        "module": "api",
        "event": "test",
        "key": "sk-abcdefghijk",
    }
    api_log.write_text(api_log.read_text(encoding="utf-8") + json.dumps(payload) + "\n", encoding="utf-8")

    assert check_logs.main(["--root", str(root), "--date", TODAY, "--since-days", "7"]) == 1
    output = capsys.readouterr().out
    assert "secret detected" in output
    assert "sk-abcdefghijk" not in output


def test_every_required_writer_has_a_log_event_callsite():
    app_root = Path(__file__).resolve().parents[2] / "app"
    callsites: set[str] = set()
    for path in app_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function = node.func
            if isinstance(function, ast.Name) and function.id == "log_event":
                module = node.args[0]
                if isinstance(module, ast.Constant) and isinstance(module.value, str):
                    callsites.add(module.value)

    assert set(check_logs.REQUIRED_WRITERS) <= callsites
