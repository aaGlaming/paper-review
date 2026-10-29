# -*- coding: utf-8 -*-
"""用赛题 PDF 的真实题面替换 contest.json 的 statement。

只改 statement 一个字段，其余字段与缩进保持原样（indent=2）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
PAPERS = PROJECT_ROOT / "data" / "papers"
STATEMENT_SUFFIX = "题.pdf"


def discover_statements() -> list[tuple[str, Path]]:
    """扫 `data/papers/<赛题>/` 下的题面 PDF，不写死题号。"""
    if not PAPERS.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for contest_dir in sorted(p for p in PAPERS.iterdir() if p.is_dir()):
        for pdf in sorted(contest_dir.glob(f"*{STATEMENT_SUFFIX}")):
            out.append((contest_dir.name, pdf))
    return out


def extract_statement(pdf: Path) -> str:
    result = subprocess.run(
        [PY, str(PROJECT_ROOT / "scripts" / "pdf_statement.py"), str(pdf)],
        check=True, capture_output=True, cwd=PROJECT_ROOT,
    )
    return result.stdout.decode("utf-8").strip()


def main() -> int:
    pairs = discover_statements()
    if not pairs:
        print(f"[跳过] {PAPERS} 下没有题面 PDF")
        return 1
    for contest_id, pdf in pairs:
        if not pdf.is_file():
            print(f"[跳过] 找不到 {pdf}")
            continue
        text = extract_statement(pdf)
        if len(text) < 200:
            print(f"[跳过] {contest_id} 提取过短（{len(text)} 字符），疑似失败")
            continue
        path = PROJECT_ROOT / "data" / "contests" / contest_id / "contest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        before = len(str(data.get("statement") or ""))
        data["statement"] = text
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[{contest_id}] statement {before} -> {len(text)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
