# -*- coding: utf-8 -*-
"""把已生成的论文 Markdown 重新整理一遍（不重跑 OCR）。

用途：OCR 已经跑完、但标题规则改过之后，用已有文本重新加标题与合并段落，
省掉重复识别的时间。

用法：
    python scripts/retitle_md.py data/samples/cumcm-2024-A-a016.md [more.md ...]
    python scripts/retitle_md.py --all      # 处理 data/samples/cumcm-*.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from md_headings import build_markdown  # noqa: E402


def retitle(path: Path) -> tuple[int, int]:
    """把已有的 # 去掉后重新组织。返回 (旧标题数, 新标题数)。"""
    text = path.read_text(encoding="utf-8")
    old_heads = sum(1 for l in text.split("\n") if l.startswith("# "))
    # 剥掉之前加的所有标题前缀，恢复成纯文本行
    plain = "\n".join(
        l[3:] if l.startswith("## ") else (l[2:] if l.startswith("# ") else l)
        for l in text.split("\n")
    )
    md = build_markdown([plain])
    path.write_text(md, encoding="utf-8")
    new_heads = sum(1 for l in md.split("\n") if l.startswith("# "))
    return old_heads, new_heads


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    targets = [Path(f) for f in args.files]
    if args.all:
        targets += sorted((ROOT / "data" / "samples").glob("cumcm-*.md"))
    if not targets:
        print("没有指定文件")
        return 1

    for p in targets:
        if not p.is_file():
            print(f"[跳过] 不存在 {p}")
            continue
        old, new = retitle(p)
        text = p.read_text(encoding="utf-8")
        print(f"{p.name}: 标题 {old} -> {new}  {len(text)} 字符")
        for line in text.split("\n"):
            if line.startswith("# "):
                print("    ", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
