# -*- coding: utf-8 -*-
"""把扫描版论文 PDF 转成系统可用的 Markdown。

背景：CUMCM 官方展示论文都是扫描件（无文本层），pdftotext 抽不出内容，
必须走「PDF 页 -> PNG -> OCR -> 文本 -> 加章节标题」。

标题与分段规则在同目录的 `md_headings.py`，与 `retitle_md.py` 共用。

用法：
    python scripts/pdf_to_md.py <input.pdf> <output.md> [--dpi 200] [--start 1] [--end N]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from md_headings import build_markdown, normalize  # noqa: E402


def run_pdftoppm(pdf: Path, out_dir: Path, dpi: int, start: int | None, end: int | None) -> list[Path]:
    cmd = ["pdftoppm", "-r", str(dpi), "-png"]
    if start:
        cmd += ["-f", str(start)]
    if end:
        cmd += ["-l", str(end)]
    cmd += [str(pdf), str(out_dir / "page")]
    subprocess.run(cmd, check=True, capture_output=True)
    files = sorted(out_dir.glob("page-*.png"))
    if not files:
        raise RuntimeError(f"pdftoppm 没有产出图片：{pdf}")
    return files


def ocr_pages(files: list[Path], engine) -> list[str]:
    texts: list[str] = []
    for index, path in enumerate(files, 1):
        result, _ = engine(str(path))
        lines = [item[1].strip() for item in (result or []) if item[1].strip()]
        texts.append("\n".join(lines))
        print(f"  OCR {index}/{len(files)}", file=sys.stderr, flush=True)
    return texts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    args = ap.parse_args()

    pdf = Path(args.pdf)
    if not pdf.is_file():
        print(f"找不到 PDF：{pdf}", file=sys.stderr)
        return 2

    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    tmp = Path(tempfile.mkdtemp(prefix="ocr_"))
    try:
        print(f"[{pdf.name}] 导出图片…", file=sys.stderr, flush=True)
        files = run_pdftoppm(pdf, tmp, args.dpi, args.start, args.end)
        print(f"[{pdf.name}] 共 {len(files)} 页，开始 OCR…", file=sys.stderr, flush=True)
        pages = [normalize(t) for t in ocr_pages(files, engine)]
        md = build_markdown(pages)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        heads = [l for l in md.split("\n") if l.startswith("#")]
        print(f"[{pdf.name}] -> {out}  {len(md)} 字符，标题 {len(heads)} 个")
        for h in heads[:10]:
            print("   ", h)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
