"""Validate the daily JSON logs without importing application code."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

MODULES = ("api", "graph", "agent", "llm", "retrieve", "scoring", "review", "report", "importing", "auth", "ai_chat", "dashboard", "errors", "audit", "frontend")
REQUIRED_WRITERS = ("api", "graph", "llm", "retrieve", "scoring", "report", "review", "importing")
# 白名单只减不增：auth 已是登录每日常态，从白名单移除；
# audit 只在权限拒绝时写，某天无拒绝即为空，允许空但不许加进必需写入者
# （加进去会让脚本在无拒绝的日子周期性误报）。
# ai_chat 只在教师使用问询时写，无问询的日子为空。
ALLOWED_EMPTY = {"errors", "ai_chat", "dashboard", "audit", "frontend", "agent"}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}"),
    re.compile(r"(?i)(?:password|passwd|pwd)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(?:api[_-]?key|secret)\s*[:=]\s*\S+"),
    re.compile(r"mysql(?:\+pymysql)?://"),
)


def _files(root: Path, module: str, day: str) -> list[Path]:
    return sorted(root.joinpath(module).glob(f"{module}-{day}.log*"))


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


def _display(line: str) -> str:
    """报错回显用：含密钥则脱敏，否则原文。脚本自己也不许把密钥原文写进 stdout。"""
    for pattern in SECRET_PATTERNS:
        match = pattern.search(line)
        if match:
            return line[: match.start()] + _redact(match.group(0)) + line[match.end() :]
    return line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    parser.add_argument("--root", default="logs")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root)
    issues = 0
    dirs = 0
    writers = 0
    for module in MODULES:
        directory = root / module
        if directory.is_dir():
            dirs += 1
        else:
            print(f"missing directory: {module}")
            issues += 1
            continue
        files = _files(root, module, args.date)
        line_count = 0
        for path in files:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                print(f"cannot read {path}: {type(exc).__name__}")
                issues += 1
                continue
            for lineno, line in enumerate(lines, 1):
                line_count += 1
                # 密钥扫描先于 JSON 解析：脏行本身可能就是密钥原文，
                # 若先 parse 失败 continue，这条就永远扫不到。
                if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                    print(f"secret detected: {path} line {lineno}: {_display(line)[:80]}")
                    issues += 1
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    print(f"invalid JSON: {path} line {lineno}: {_display(line)[:80]}")
                    issues += 1
                    continue
                if not all(key in payload for key in ("ts", "level", "module", "event")):
                    print(f"missing fields: {path} line {lineno}")
                    issues += 1
                if payload.get("module") != module:
                    print(f"module mismatch: {path} line {lineno}: {payload.get('module')!r}")
                    issues += 1
        if module in REQUIRED_WRITERS:
            if line_count:
                writers += 1
            else:
                print(f"required writer empty: {module}")
                issues += 1
        elif not line_count and args.verbose:
            print(f"allowed empty: {module}")
    if issues:
        print(f"[fail] {issues} issues")
        return 1
    print(f"[ok] {dirs} dirs, {writers} writers, 0 issue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
