# -*- coding: utf-8 -*-
"""批量把 data/papers/<赛题>/*.pdf 转成 data/samples/*.md（并行）。

输入按赛题分目录归档，赛题列表由 `data/papers/` 下的子目录自动发现，
新增赛题不需要改代码。题面 PDF（文件名以「题」结尾）不属于论文，跳过。

命名规则：<contest_id>-<论文编号小写>.md，例如 cumcm-2024-A-a016.md。
已存在的输出会跳过（除非加 --force）。

用法：
    python scripts/batch_papers.py                 # 转缺失的，默认 4 路并行
    python scripts/batch_papers.py --workers 2     # 降低并发（内存紧张时）
    python scripts/batch_papers.py --force         # 全部重转
    python scripts/batch_papers.py --only A053     # 只转文件名含该串的
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SAMPLES = PROJECT_ROOT / "data" / "samples"
PAPERS = PROJECT_ROOT / "data" / "papers"

# 题面文件名形如「A题.pdf」「C题.pdf」，不是参赛论文
STATEMENT_SUFFIX = "题.pdf"


def discover_contests() -> list[str]:
    """按 `data/papers/` 的子目录发现赛题，不写死题号。"""
    if not PAPERS.is_dir():
        return []
    return sorted(p.name for p in PAPERS.iterdir() if p.is_dir())


def collect() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for contest_id in discover_contests():
        paper_dir = PAPERS / contest_id
        for pdf in sorted(paper_dir.glob("*.pdf")):
            if pdf.name.endswith(STATEMENT_SUFFIX):
                continue
            stem = pdf.stem.lower().replace(" ", "")
            pairs.append((pdf, SAMPLES / f"{contest_id}-{stem}.md"))
    return pairs


def convert(pdf: Path, out: Path, dpi: int) -> tuple[Path, int, float, str]:
    started = time.time()
    result = subprocess.run(
        [PY, str(PROJECT_ROOT / "scripts" / "pdf_to_md.py"),
         str(pdf), str(out), "--dpi", str(dpi)],
        cwd=PROJECT_ROOT, capture_output=True,
    )
    cost = time.time() - started
    err = result.stderr.decode("utf-8", errors="replace")[-300:]
    return pdf, result.returncode, cost, err


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    pairs = collect()
    if args.only:
        key = args.only.lower()
        pairs = [(p, o) for p, o in pairs if key in p.stem.lower()]
    if not pairs:
        print("没有找到待处理的 PDF")
        return 1

    todo = [(p, o) for p, o in pairs if args.force or not o.exists()]
    print(f"共 {len(pairs)} 篇，待转 {len(todo)} 篇，并发 {args.workers}")
    for p, o in pairs:
        print(f"  [{'待转' if (p, o) in todo else '已存在'}] {p.name:12s} -> {o.name}")
    if not todo:
        return 0

    ok = fail = 0
    started_all = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(convert, p, o, args.dpi): (p, o) for p, o in todo}
        for done, future in enumerate(as_completed(futures), 1):
            pdf, code, cost, err = future.result()
            out = futures[future][1]
            if code == 0 and out.exists():
                ok += 1
                print(f"[{done}/{len(todo)}] OK {out.name}  "
                      f"{out.stat().st_size} B  {cost:.0f}s", flush=True)
            else:
                fail += 1
                print(f"[{done}/{len(todo)}] FAIL {pdf.name}  {cost:.0f}s\n{err}",
                      flush=True)

    print(f"\n完成：成功 {ok}，失败 {fail}，总耗时 {time.time() - started_all:.0f}s")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
