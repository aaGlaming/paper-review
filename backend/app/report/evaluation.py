"""评测：把已定的系统档位与 gold 对比，输出三项指标。

三项指标的口径写在每个指标的 `caliber` 字段里：
- 档位一致率 = 系统档位与 gold 档位一致的维度数 / 有 gold 的维度总数；
- 引用精确匹配率 = 原句逐字出现在所引父块里的维度数 / 给出原句的维度数；
- 证据不足命中情况 = gold 为证据不足且系统也判证据不足的维度数 / gold 为证据不足的维度数。

本模块是纯计算：不连数据库、不发 HTTP、不调模型。系统档位的来源由调用方决定——
`run_eval(chat=...)` 注入模型时走真实选档（`source="model"`）；`chat=None` 走**确定性结构回退**
（`source="deterministic"`）：回退只按章节结构判「这一维有没有可引用的正文」，因此它给出的数字是
**脚本自检**，不是模型准确率。代码里不写死任何目标准确率：指标是输出，不是断言。

分母口径偏差：`data/samples/` 下三篇演示稿没有 gold 元数据（只有 `data/samples/eval/` 的 12 篇有），
而 `data/samples/` 不在 v0.8.0 允许修改范围，所以返回结果里同时给出**语料片数**（15）与
**有 gold 的可算样本**（12 篇 / 60 个维度项），三项指标的分子分母都按可算样本计算。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..review import samples as review_samples
from ..review.consistency import section_spans

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONTESTS_DIR = PROJECT_ROOT / "data" / "contests"

INSUFFICIENT_BAND = "证据不足"
FALLBACK_BAND = "基本"
SOURCE_MODEL = "model"
SOURCE_DETERMINISTIC = "deterministic"
NO_SAMPLES = "无可算样本"

CALIBER_BAND = "档位一致率 = 系统档位与 gold 档位一致的维度数 / 有 gold 的维度总数"
CALIBER_QUOTE = "引用精确匹配率 = 原句逐字出现在所引父块里的维度数 / 给出原句的维度数"
CALIBER_INSUFFICIENT = (
    "证据不足命中情况 = gold 为证据不足且系统也判证据不足的维度数 / gold 为证据不足的维度数"
)


def _metric(matched: int, total: int, caliber: str) -> dict[str, Any]:
    if total <= 0:
        return {
            "matched": 0,
            "total": 0,
            "rate": None,
            "caliber": f"{caliber}；当前{NO_SAMPLES}（分母为 0）",
        }
    return {"matched": matched, "total": total, "rate": matched / total, "caliber": caliber}


def _width(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def _index(results: Any) -> dict[str, dict[str, Any]]:
    if isinstance(results, Mapping):
        items = [
            {"dimension_code": code, **(value if isinstance(value, Mapping) else {})}
            for code, value in results.items()
        ]
    else:
        items = list(results or ())
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        code = str(item.get("dimension_code") or item.get("code") or "")
        if code:
            indexed[code] = dict(item)
    return indexed


def summarize_eval(
    pairs: Iterable[Sequence[Any]],
    *,
    corpus_papers: int = 0,
    source: str = SOURCE_DETERMINISTIC,
) -> dict[str, Any]:
    """`pairs` 的每一项是 (gold, system_result, quote_check)。

    `gold` 是 [{dimension_code, band}]，`system_result` 是系统给出的各维结果，
    `quote_check` 是 {dimension_code: 原句是否逐字出现在它引用的父块里}。
    """
    band_matched = band_total = 0
    quote_matched = quote_total = 0
    insufficient_matched = insufficient_total = 0
    gradable_papers = 0

    for pair in pairs:
        gold, system, quote_check = (list(pair) + [None, None, None])[:3]
        gradable_papers += 1
        indexed = _index(system)
        checks = quote_check if isinstance(quote_check, Mapping) else {}
        for item in gold or ():
            if not isinstance(item, Mapping):
                continue
            code = str(item.get("dimension_code") or "")
            band = item.get("band")
            got = indexed.get(code) or {}
            band_total += 1
            if band is not None and got.get("band") == band:
                band_matched += 1
            if band == INSUFFICIENT_BAND:
                insufficient_total += 1
                if got.get("band") == INSUFFICIENT_BAND:
                    insufficient_matched += 1
            if got.get("quote"):
                quote_total += 1
                if bool(checks.get(code)):
                    quote_matched += 1

    outcome = {
        "corpus_papers": int(corpus_papers),
        "gradable_papers": gradable_papers,
        "gradable_dimensions": band_total,
        "source": source,
        "band_agreement": _metric(band_matched, band_total, CALIBER_BAND),
        "quote_exact_match": _metric(quote_matched, quote_total, CALIBER_QUOTE),
        "insufficient_evidence_hit": _metric(
            insufficient_matched, insufficient_total, CALIBER_INSUFFICIENT
        ),
        "no_samples": band_total == 0,
        "note": (
            "分子分母都按有 gold 的可算样本计算；三篇演示稿没有 gold，不计入分母。"
            "source=deterministic 时这些数字是确定性结构回退的脚本自检，不是模型准确率。"
        ),
    }
    return outcome


# --- 数据准备 ------------------------------------------------------------------


def _bodies(text: str) -> list[dict[str, str]]:
    spans = section_spans(text)
    bodies: list[dict[str, str]] = []
    for span in spans:
        body = text[int(span["char_start"]) : int(span["char_end"])]
        bodies.append({"title": str(span["title"]), "text": body})
    return bodies


def _load_rubric(contest_id: str) -> dict[str, Any]:
    """只读赛题目录里的量规与约束。找不到就返回空表，评测按无维度处理。"""
    import json

    base = CONTESTS_DIR / str(contest_id)
    rubric_path = base / "rubric.json"
    constraints_path = base / "constraints.json"
    dimensions: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []
    if rubric_path.is_file():
        payload = json.loads(rubric_path.read_text(encoding="utf-8"))
        for item in payload.get("dimensions") or ():
            dimensions.append(
                {
                    "dimension_code": str(item.get("code") or item.get("dimension_code") or ""),
                    "name": str(item.get("name") or ""),
                    "weight": _width(item.get("weight")),
                    "section_types": [str(value) for value in (item.get("section_types") or ())],
                }
            )
    if constraints_path.is_file():
        payload = json.loads(constraints_path.read_text(encoding="utf-8"))
        constraints = [dict(item) for item in payload.get("constraints") or ()]
    return {"dimensions": dimensions, "constraints": constraints}


def _matching_sections(text: str, section_types: Sequence[str]) -> list[dict[str, str]]:
    wanted = [str(item) for item in section_types or () if str(item).strip()]
    matched: list[dict[str, str]] = []
    for body in _bodies(text):
        if not body["text"].strip():
            continue
        if any(flag in body["title"] for flag in wanted):
            matched.append(body)
    return matched


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def deterministic_results(text: str, dimensions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """确定性结构回退：该维有可引用的章节正文就给「基本」并抄一句原话，没有就判证据不足。"""
    results: list[dict[str, Any]] = []
    for dimension in dimensions or ():
        code = str(dimension.get("dimension_code") or "")
        if not code:
            continue
        matched = _matching_sections(text, dimension.get("section_types") or ())
        if not matched:
            results.append(
                {
                    "dimension_code": code,
                    "band": INSUFFICIENT_BAND,
                    "status": INSUFFICIENT_BAND,
                    "quote": None,
                    "chunk_ids": [],
                }
            )
            continue
        results.append(
            {
                "dimension_code": code,
                "band": FALLBACK_BAND,
                "status": FALLBACK_BAND,
                "quote": _first_line(matched[0]["text"]),
                "chunk_ids": [],
            }
        )
    return results


def _graph_retriever(text: str, dimensions: Sequence[Mapping[str, Any]]):
    """给状态图用的内存检索器：直接用稿子里对应章节的正文当父块，不读向量库。"""
    section_types_by_code = {
        str(dimension.get("dimension_code") or ""): list(dimension.get("section_types") or ())
        for dimension in dimensions or ()
    }
    sections = _bodies(text)

    def retriever(request) -> dict[str, Any]:
        code = request.dimension_code
        wanted = [str(flag) for flag in section_types_by_code.get(code, ()) if str(flag).strip()]
        matched = [
            body
            for body in sections
            if body["text"].strip() and any(flag in body["title"] for flag in wanted)
        ]
        parents = [
            {
                "parent_id": f"{code}-{index}",
                "section_type": body["title"],
                "content": body["text"],
                "chunk_ids": [f"{code}-{index}-00"],
                "review_id": request.review_id,
            }
            for index, body in enumerate(matched)
        ]
        return {
            "status": "命中" if parents else INSUFFICIENT_BAND,
            "rounds": 1,
            "parents": parents,
            "queries": [code],
        }

    return retriever


def _graph_results(
    text: str,
    dimensions: Sequence[Mapping[str, Any]],
    constraints: Sequence[Mapping[str, Any]],
    chat,
) -> list[dict[str, Any]]:
    """走真实选档：把 chat 原样传给状态图，档位由模型给出。"""
    from ..graph.review_graph import build_review_graph, create_review, resume_review

    graph = build_review_graph(
        retriever=_graph_retriever(text, dimensions),
        chat=chat,
        rubric_dimensions=dimensions,
        constraints=constraints,
    )
    review_id = create_review(text, graph=graph)
    config = {"configurable": {"thread_id": review_id}}
    sections = (graph.get_state(config).values or {}).get("sections") or []
    final = resume_review(review_id, sections, graph=graph)
    results = final.get("dimension_results") or {}
    return [{"dimension_code": code, **dict(value)} for code, value in results.items()]


def run_eval(chat=None, *, eval_dir: str | Path | None = None) -> dict[str, Any]:
    """跑一遍评测，返回口径、来源与三项指标。"""
    papers = review_samples.load_eval_papers(eval_dir)
    demo_papers = len(review_samples.DEMO_FILES)
    source = SOURCE_MODEL if chat is not None else SOURCE_DETERMINISTIC

    pairs: list[tuple[Any, Any, Any]] = []
    for paper in papers:
        text = str(paper.get("text") or "")
        rubric = _load_rubric(str(paper.get("contest_id") or ""))
        dimensions = rubric["dimensions"]
        if chat is None:
            system = deterministic_results(text, dimensions)
        else:
            system = _graph_results(text, dimensions, rubric["constraints"], chat)
        quote_check = {
            str(item.get("dimension_code") or ""): bool(item.get("quote"))
            and str(item.get("quote")) in text
            for item in system
        }
        pairs.append((paper.get("gold") or [], system, quote_check))

    outcome = summarize_eval(pairs, corpus_papers=len(papers) + demo_papers, source=source)
    outcome["demo_papers_without_gold"] = demo_papers
    return outcome
