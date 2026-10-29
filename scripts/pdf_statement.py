# -*- coding: utf-8 -*-
"""从赛题 PDF 提取干净题面，用于更新 contest.json 的 statement。

赛题 PDF 有文本层（与论文不同），但 pdftotext 会带出图注、表格头、页码碎片，
且正文按版面硬换行。

清洗原则：**宁可保留噪音，不可丢题面数据**。
题目里的坐标、数值是评审的关键依据，错删一行可能就让 constraint_check 失效。
因此只删「确定是排版噪音」的行，其余一律保留。

用法：
    python scripts/pdf_statement.py <contest.pdf> [--out path.txt]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 只删这几类：版式噪音（不是题目内容）
NOISE_PATTERNS = (
    re.compile(r"^图\s*\d+\s"),                    # 图注：以「图 1 xxx」开头
    re.compile(r"^表\s*\d+\s"),                    # 表注
    re.compile(r"^\d{1,3}$"),                      # 页码
    re.compile(r"^[-—_=\s]{3,}$"),                 # 分隔线
    re.compile(r"^高教社杯全国大学生数学建模竞赛题目$"),
    re.compile(r"^（请先阅读"),                     # 格式规范提示
    re.compile(r"^第\s*\d+\s*页"),
)

# 这些行单独成段（标题 / 编号问题）
NEW_PARA = re.compile(
    r"^\s*("
    r"[A-E]\s*题"                    # A 题 …
    r"|问题\s*\d"                    # 问题 1 …
    r"|第[一二三四五六七八九十]+\s*问"
    r"|请建立|请给出|请针对|请确定"
    r"|附件\s*\d"
    r"|附录"
    r")"
)
# 段落终止标点：以这些结尾就不再与下一行合并
END_PUNCT = ("。", "？", "！", "；", "”", "）", "》")

# 标题行：本身独立成段，且不吸收下一行
HEADING = re.compile(r"^\s*([A-E]\s*题\s|.*年高教社杯.*题目\s*$|[A-E]\s*题$)")

# 少数 PDF 用特殊字体排数学符号，提取后变成替换符；按题意补回
SYMBOL_FIXES = (
    ("水平面为 \ufffd\ufffd\ufffd\ufffd\ufffd\ufffd平面", "水平面为 xOy 平面"),
    ("\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd", "xOy"),
)


def extract(pdf: Path) -> str:
    raw = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", "-layout", str(pdf), "-"],
        check=True, capture_output=True,
    ).stdout.decode("utf-8", errors="replace")

    kept: list[str] = []
    for ln in raw.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if any(p.search(s) for p in NOISE_PATTERNS):
            continue
        # 至少要有一个汉字，纯符号行丢弃
        if not any("\u4e00" <= c <= "\u9fff" for c in s):
            continue
        kept.append(s)

    # 合并断行：上一条没结束、本条不是新段落开头、上一条也不是标题，才接上
    merged: list[str] = []
    for s in kept:
        prev = merged[-1] if merged else None
        joinable = (
            prev is not None
            and not prev.endswith(END_PUNCT)
            and not NEW_PARA.match(s)
            and not HEADING.match(prev)
        )
        if joinable:
            merged[-1] = prev + s
        else:
            merged.append(s)

    text = "\n\n".join(merged).strip() + "\n"
    for bad, good in SYMBOL_FIXES:
        text = text.replace(bad, good)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    pdf = Path(args.pdf)
    if not pdf.is_file():
        print(f"找不到 PDF：{pdf}", file=sys.stderr)
        return 2

    text = extract(pdf)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"-> {out}  {len(text)} 字符")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
