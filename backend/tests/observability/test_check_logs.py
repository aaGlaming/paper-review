import json
from pathlib import Path

from scripts import check_logs


DAY = "20261020"


def _root(tmp_path: Path, *, valid=True) -> Path:
    for module in check_logs.MODULES:
        directory = tmp_path / module
        directory.mkdir()
        if module in check_logs.REQUIRED_WRITERS:
            payload = {"ts": "2026-10-20T00:00:00+08:00", "level": "INFO", "module": module, "event": "test"}
            (directory / f"{module}-{DAY}.log").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_check_logs_valid(tmp_path, capsys):
    assert check_logs.main(["--root", str(_root(tmp_path)), "--date", DAY]) == 0
    assert "[ok] 15 dirs, 8 writers, 0 issue" in capsys.readouterr().out


def test_check_logs_redacts_secret(tmp_path, capsys):
    root = _root(tmp_path)
    path = root / "api" / f"api-{DAY}.log"
    path.write_text(path.read_text(encoding="utf-8") + 'sk-abcdefghij1234\n', encoding="utf-8")
    assert check_logs.main(["--root", str(root), "--date", DAY]) == 1
    output = capsys.readouterr().out
    assert "secret detected" in output
    assert "sk-abcdefghij1234" not in output


def test_check_logs_invalid_json_has_line(tmp_path, capsys):
    root = _root(tmp_path)
    (root / "api" / f"api-{DAY}.log").write_text("bad\n", encoding="utf-8")
    assert check_logs.main(["--root", str(root), "--date", DAY]) == 1
    assert "line 1" in capsys.readouterr().out


def test_check_logs_module_mismatch(tmp_path, capsys):
    root = _root(tmp_path)
    path = root / "api" / f"api-{DAY}.log"
    path.write_text(json.dumps({"ts": "x", "level": "INFO", "module": "graph", "event": "x"}), encoding="utf-8")
    assert check_logs.main(["--root", str(root), "--date", DAY]) == 1
    assert "module mismatch" in capsys.readouterr().out


def test_check_logs_required_writer_empty(tmp_path, capsys):
    root = _root(tmp_path)
    (root / "report" / f"report-{DAY}.log").unlink()
    assert check_logs.main(["--root", str(root), "--date", DAY]) == 1
    assert "required writer empty: report" in capsys.readouterr().out
