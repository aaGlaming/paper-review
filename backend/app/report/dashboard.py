"""Read-only dashboard aggregations, cached in-process for sixty seconds."""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, time as datetime_time, timedelta
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Review, ReviewDimension

_TTL_SECONDS = 60.0
_clock: Callable[[], float] = time.monotonic
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_RAW_BANDS = ("充分", "基本", "不足", "证据不足")
_SCORED = Review.rubric_id != ""


def clear_cache() -> None:
    _cache.clear()


def _cached(key: str, session: Session, builder: Callable[[Session], dict[str, Any]]) -> dict[str, Any]:
    now = _clock()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < _TTL_SECONDS:
        return {**hit[1], "cached": True}
    result = builder(session)
    _cache[key] = (now, result)
    return {**result, "cached": False}


def _normalize_band(value: Any) -> str | None:
    """Single dashboard rate-caliber rule: both insufficient labels share one bucket."""
    if value in ("不足", "证据不足"):
        return "证据不足"
    return str(value) if value is not None else None


def _gold_agreement() -> dict[str, Any] | None:
    """Return deterministic sample-vs-gold agreement using normalized bands."""
    from . import evaluation
    from ..review import samples

    papers = samples.load_eval_papers()
    if not papers:
        return None
    matched = total = 0
    for paper in papers:
        contest_id = str(paper.get("contest_id") or "")
        rubric = evaluation._load_rubric(contest_id)
        system = evaluation.deterministic_results(
            str(paper.get("text") or ""), rubric["dimensions"]
        )
        system_by_code = {
            str(item.get("dimension_code") or ""): item for item in system
        }
        for gold in paper.get("gold") or ():
            code = str(gold.get("dimension_code") or "")
            expected = _normalize_band(gold.get("band"))
            actual = _normalize_band((system_by_code.get(code) or {}).get("band"))
            total += 1
            if expected is not None and actual == expected:
                matched += 1
    if total == 0:
        return None
    return {
        "agreement": matched / total,
        "matched": matched,
        "total": total,
        "source": "deterministic",
    }


def _conflicts(session: Session) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Decode only the small JSON column; relational aggregation remains in SQL."""
    rows = session.execute(select(Review.review_id, Review.change_list).order_by(Review.review_id)).all()
    kinds: Counter[str] = Counter()
    targets: Counter[str] = Counter()
    finding_total = 0
    for review_id, raw in rows:
        try:
            changes = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(changes, list):
            continue
        for item in changes:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip()
            target = str(item.get("target") or "").strip()
            if kind:
                kinds[kind] += 1
            if target:
                targets[target] += 1
            if item.get("finding_kind"):
                finding_total += 1
    return (
        [{"kind": key, "count": count} for key, count in sorted(kinds.items())],
        [{"target": key, "count": count} for key, count in sorted(targets.items(), key=lambda row: (-row[1], row[0]))[:10]],
        finding_total,
    )


def _build_summary(session: Session) -> dict[str, Any]:
    now = datetime.utcnow()
    total_reviews = int(session.scalar(select(func.count()).select_from(Review).where(_SCORED)) or 0)
    parse_only = int(
        session.scalar(select(func.count()).select_from(Review).where(Review.rubric_id == "")) or 0
    )
    weekly_new = int(session.scalar(
        select(func.count()).select_from(Review).where(
            _SCORED, Review.created_at >= now - timedelta(days=7)
        )
    ) or 0)

    contests = [
        {"contest_id": str(contest_id or ""), "review_count": int(count)}
        for contest_id, count in session.execute(
            select(Review.contest_id, func.count())
            .where(_SCORED)
            .group_by(Review.contest_id)
            .order_by(Review.contest_id)
        ).all()
    ]

    grouped_bands: dict[str, dict[str, int]] = {}
    for dimension, band, count in session.execute(
        select(ReviewDimension.dimension_code, ReviewDimension.band, func.count())
        .join(Review, Review.review_id == ReviewDimension.review_id)
        .group_by(ReviewDimension.dimension_code, ReviewDimension.band)
    ).all():
        dimension_code = str(dimension)
        raw_band = str(band) if band is not None else "未选档"
        grouped_bands.setdefault(dimension_code, {})[raw_band] = int(count)
    bands = []
    for dimension_code, existing in sorted(grouped_bands.items()):
        counts = {key: int(existing.get(key, 0)) for key in _RAW_BANDS}
        insufficient_total = counts["不足"] + counts["证据不足"]
        bands.append({
            "dimension_code": dimension_code,
            "counts": counts,
            "insufficient_total": insufficient_total,
        })
    insufficient_top = sorted(
        bands, key=lambda item: (-item["insufficient_total"], item["dimension_code"])
    )

    status_counts = session.execute(
        select(ReviewDimension.status, func.count()).group_by(ReviewDimension.status)
    ).all()
    total_dimensions = sum(int(count) for _, count in status_counts)
    citation_failures = sum(int(count) for status, count in status_counts if status == "引用失败")
    citation_rate = citation_failures / total_dimensions if total_dimensions else 0.0
    conflict_types, conflict_targets, pending_conflicts = _conflicts(session)
    gold = _gold_agreement()

    return {
        "cards": {
            "total_submissions": total_reviews,
            "weekly_new": weekly_new,
            "parse_only": parse_only,
            "pending_conflicts": pending_conflicts,
            "gold_agreement": gold,
        },
        "contests": contests,
        "bands": bands,
        "insufficient_top": insufficient_top,
        "conflicts": conflict_types,
        "hotspots": conflict_targets,
        "citation": {
            "failure_count": citation_failures,
            "total_dimensions": total_dimensions,
            "citation_rate": citation_rate,
        },
        "gold": gold,
    }


def get_summary(session: Session) -> dict[str, Any]:
    return _cached("summary", session, _build_summary)


def _build_trend(session: Session, days: int) -> dict[str, Any]:
    # Review.created_at is stored as naive UTC by report.models.utc_now().
    today = datetime.utcnow().date()
    start_day = today - timedelta(days=days - 1)
    start = datetime.combine(start_day, datetime_time.min)
    rows = session.execute(
        select(func.date(Review.created_at), Review.user_id.is_(None), func.count())
        .where(_SCORED, Review.created_at >= start)
        .group_by(func.date(Review.created_at), Review.user_id.is_(None))
    ).all()
    grouped: dict[str, dict[str, int]] = {}
    for day_value, ownerless, count in rows:
        day_text = day_value.isoformat() if hasattr(day_value, "isoformat") else str(day_value)
        bucket = grouped.setdefault(day_text, {"total": 0, "ownerless": 0})
        bucket["total"] += int(count)
        if bool(ownerless):
            bucket["ownerless"] += int(count)
    series = []
    for offset in range(days):
        day_text = (start_day + timedelta(days=offset)).isoformat()
        bucket = grouped.get(day_text, {"total": 0, "ownerless": 0})
        series.append({"date": day_text, **bucket})
    return {"days": days, "series": series}


def get_trend(session: Session, days: int) -> dict[str, Any]:
    return _cached(f"trend:{days}", session, lambda db: _build_trend(db, days))

