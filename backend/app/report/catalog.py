"""样例目录：三篇演示稿与评测论文的列表。

演示稿放在 `data/samples/` 根下、评测论文放在 `data/samples/eval/` 下，按位置区分 `is_demo`：
根下的三篇是演示样例，`eval/` 下的带 gold，是评测样本。目录说明文件不算样例。
本模块只读文件，不连数据库、不发 HTTP、不调模型。
"""

from __future__ import annotations

from typing import Any

from ..review import samples as review_samples


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def list_samples(is_demo: bool | None = None) -> list[dict[str, Any]]:
    """列出样例。`is_demo=None` 时三篇演示与全部评测论文都返回。"""
    entries: list[dict[str, Any]] = []
    for stem, text in review_samples.load_demo_texts().items():
        entries.append(
            {
                "sample_id": stem,
                "title": _title(text, stem),
                "is_demo": True,
                "contest_id": "",
                "has_gold": False,
            }
        )
    for paper in review_samples.load_eval_papers():
        entries.append(
            {
                "sample_id": str(paper["paper_id"]),
                "title": str(paper["title"]),
                "is_demo": False,
                "contest_id": str(paper.get("contest_id") or ""),
                "has_gold": bool(paper.get("gold")),
            }
        )
    if is_demo is None:
        return entries
    return [entry for entry in entries if entry["is_demo"] is bool(is_demo)]
