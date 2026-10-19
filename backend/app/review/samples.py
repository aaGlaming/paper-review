"""样例读入：三篇演示稿的正文，以及评测论文的正文与元数据。

只做文件读入，不连数据库、不发 HTTP、不调模型；审查逻辑在 `consistency.py`。
评测样例的元数据放在同名 `.json` 里，字段为 `paper_id`、`contest_id`、`title`、`gold`、
`expected_findings`。本版只要求能被读入，档位一致率等对比计算放到 v0.8.0。
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"
EVAL_DIR = SAMPLES_DIR / "eval"

DEMO_FILES: tuple[str, ...] = ("bench-dragon.md", "planting.md", "smoke.md")
# 真实参赛论文与演示稿放在同一目录，靠 DEMO_FILES 排除，不按赛题名匹配
# （架构约束：不得按题号分支，见 backend/tests/review/test_demo_conflicts.py）。
REQUIRED_EVAL_FIELDS: tuple[str, ...] = ("paper_id", "title", "gold", "expected_findings")
GOLD_FIELDS: tuple[str, ...] = ("dimension_code", "band")


def load_demo_text(filename: str, directory: str | Path | None = None) -> str:
    """读一篇演示稿的正文。"""
    base = Path(directory) if directory is not None else SAMPLES_DIR
    path = base / filename
    if not path.is_file():
        raise FileNotFoundError(f"找不到演示稿：{path}")
    return path.read_text(encoding="utf-8")


def load_demo_texts(directory: str | Path | None = None) -> dict[str, str]:
    """读三篇演示稿的正文，key 取文件名（不含扩展名）。"""
    return {Path(name).stem: load_demo_text(name, directory) for name in DEMO_FILES}


def load_real_papers(directory: str | Path | None = None) -> dict[str, str]:
    """读真实参赛论文：目录下除演示稿与 README 之外的 `.md`。

    没有真实论文时返回空字典；调用方自行决定是否回退到演示稿。
    """
    base = Path(directory) if directory is not None else SAMPLES_DIR
    if not base.is_dir():
        return {}
    skip = set(DEMO_FILES)
    papers: dict[str, str] = {}
    for path in sorted(base.glob("*.md")):
        if path.name in skip or path.stem.upper().startswith("README"):
            continue
        papers[path.stem] = path.read_text(encoding="utf-8")
    return papers


def contest_from_stem(stem: str) -> str:
    """从真实论文文件名推断所属赛题：去掉最后一段编号。

    例：`<赛题ID>-<论文编号>` -> `<赛题ID>`。
    源码里不写具体赛题名（架构约束：不得按题号分支，见 test_demo_conflicts）。
    """
    if not stem:
        return ""
    head, sep, tail = stem.rpartition("-")
    return head if sep and tail else ""


def load_eval_papers(directory: str | Path | None = None) -> list[dict[str, object]]:
    """读评测论文：正文取同名 md，元数据取同名 json。按文件名排序，结果稳定。"""
    base = Path(directory) if directory is not None else EVAL_DIR
    if not base.is_dir():
        raise FileNotFoundError(f"找不到评测样例目录：{base}")

    papers: list[dict[str, object]] = []
    for text_path in sorted(base.glob("*.md")):
        if text_path.stem.upper().startswith("README"):
            continue  # 目录说明不是评测样例
        meta_path = text_path.with_suffix(".json")
        if not meta_path.is_file():
            raise FileNotFoundError(f"评测样例 {text_path.name} 缺少同名元数据：{meta_path.name}")
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        for field in REQUIRED_EVAL_FIELDS:
            if field not in metadata or metadata[field] in (None, "", []):
                raise ValueError(f"{meta_path.name} 缺字段 {field}")
        gold = metadata["gold"]
        if not isinstance(gold, list) or not gold:
            raise ValueError(f"{meta_path.name} 的 gold 必须是非空数组")
        for item in gold:
            if not isinstance(item, dict) or any(field not in item for field in GOLD_FIELDS):
                raise ValueError(f"{meta_path.name} 的 gold 每项都要有 {GOLD_FIELDS}")
        papers.append(
            {
                "paper_id": str(metadata["paper_id"]),
                "contest_id": str(metadata.get("contest_id") or ""),
                "title": str(metadata["title"]),
                "text": text_path.read_text(encoding="utf-8"),
                "gold": gold,
                "expected_findings": list(metadata["expected_findings"]),
            }
        )
    return papers
