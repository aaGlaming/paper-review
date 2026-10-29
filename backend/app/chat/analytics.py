"""问询聚合统计：数字仅由数据库查询与 Python 计算产生。"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..report.models import Review, ReviewDimension


INSUFFICIENT_BANDS = ("证据不足", "不足")


def _contest(value: str) -> str:
    contest_id = str(value or "").strip()
    if not contest_id:
        raise ValueError("缺少赛题范围")
    return contest_id


def compare_bands(session: Session, *, contest_id: str) -> dict[str, Any]:
    contest_id = _contest(contest_id)
    reviews = int(session.scalar(
        select(func.count()).select_from(Review).where(Review.contest_id == contest_id)
    ) or 0)
    students = int(session.scalar(
        select(func.count(func.distinct(Review.user_id)))
        .where(Review.contest_id == contest_id, Review.user_id.is_not(None))
    ) or 0)
    orphan_reviews = int(session.scalar(
        select(func.count()).select_from(Review)
        .where(Review.contest_id == contest_id, Review.user_id.is_(None))
    ) or 0)

    rows = session.execute(
        select(ReviewDimension.dimension_code, ReviewDimension.band, func.count())
        .join(Review, Review.review_id == ReviewDimension.review_id)
        .where(Review.contest_id == contest_id)
        .group_by(ReviewDimension.dimension_code, ReviewDimension.band)
    ).all()
    grouped: dict[str, dict[str, int]] = defaultdict(dict)
    dimension_reviews: Counter[str] = Counter()
    insufficient_by_dimension: Counter[str] = Counter()
    for dimension_code, band_value, count in rows:
        dimension = str(dimension_code)
        band = str(band_value) if band_value is not None else "未选档"
        number = int(count)
        grouped[dimension][band] = number
        dimension_reviews[dimension] += number
        if band_value in INSUFFICIENT_BANDS:
            insufficient_by_dimension[dimension] += number

    bands = [
        {
            "dimension_code": dimension,
            "counts": dict(sorted(counts.items())),
            "counts_normalized": dict(sorted(
                _normalize_band_counts(counts).items()
            )),
            "insufficient": insufficient_by_dimension[dimension],
            "reviews": dimension_reviews[dimension],
        }
        for dimension, counts in sorted(grouped.items())
    ]
    return {
        "contest_id": contest_id,
        "reviews": reviews,
        "students": students,
        "orphan_reviews": orphan_reviews,
        "bands": bands,
        "insufficient_total": sum(insufficient_by_dimension.values()),
    }


def _normalize_band_counts(counts: dict[str, int]) -> dict[str, int]:
    normalized: Counter[str] = Counter()
    for band, count in counts.items():
        key = "证据不足" if band in INSUFFICIENT_BANDS else band
        normalized[key] += count
    return dict(normalized)


def _decode_change_list(raw: Any) -> tuple[list[dict[str, Any]], bool]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return [], True
    if raw is None:
        return [], False
    if not isinstance(raw, list):
        return [], True
    parsed: list[dict[str, Any]] = []
    malformed = False
    for item in raw:
        if isinstance(item, dict):
            parsed.append(item)
        else:
            malformed = True
    return parsed, malformed


def summarize_conflicts(
    session: Session,
    *,
    contest_id: str,
    top: int = 5,
) -> dict[str, Any]:
    contest_id = _contest(contest_id)
    limit = max(0, int(top))
    rows = session.execute(text(
        "SELECT review_id, change_list FROM review WHERE contest_id = :contest_id ORDER BY review_id"
    ), {"contest_id": contest_id}).all()

    reviews_with_changes = 0
    finding_total = 0
    unparsable = 0
    kinds: Counter[str] = Counter()
    targets: dict[str, dict[str, Any]] = {}
    for review_id_value, raw in rows:
        review_id = str(review_id_value)
        changes, malformed = _decode_change_list(raw)
        if malformed:
            unparsable += 1
        if changes:
            reviews_with_changes += 1
        for item in changes:
            kind = str(item.get("kind") or "").strip()
            if kind:
                kinds[kind] += 1
            if item.get("finding_kind"):
                finding_total += 1
            target = str(item.get("target") or "").strip()
            if target:
                aggregate = targets.setdefault(target, {"count": 0, "review_ids": set()})
                aggregate["count"] += 1
                aggregate["review_ids"].add(review_id)

    ordered_targets = sorted(targets.items(), key=lambda pair: (-pair[1]["count"], pair[0]))[:limit]
    hotspots = [
        {"target": target, "count": value["count"],
         "review_ids": sorted(value["review_ids"])[:3]}
        for target, value in ordered_targets
    ]
    return {
        "contest_id": contest_id,
        "reviews_with_changes": reviews_with_changes,
        "kinds": dict(sorted(kinds.items())),
        "hotspots": hotspots,
        "finding_total": finding_total,
        "unparsable": unparsable,
    }


def evidence_gaps(
    session: Session,
    *,
    contest_id: str,
    dimension_code: str | None = None,
) -> dict[str, Any]:
    contest_id = _contest(contest_id)
    statement = (
        select(ReviewDimension.review_id, ReviewDimension.dimension_code,
               ReviewDimension.band, ReviewDimension.quote)
        .join(Review, Review.review_id == ReviewDimension.review_id)
        .where(Review.contest_id == contest_id, ReviewDimension.band.in_(INSUFFICIENT_BANDS))
        .order_by(ReviewDimension.review_id, ReviewDimension.dimension_code)
    )
    if dimension_code:
        statement = statement.where(ReviewDimension.dimension_code == dimension_code)
    gaps = [
        {
            "review_id": str(review_id),
            "dimension_code": str(dimension),
            "band": str(band),
            "has_quote": bool(str(quote or "").strip()),
        }
        for review_id, dimension, band, quote in session.execute(statement).all()
        if not str(quote or "").strip()
    ]
    return {
        "contest_id": contest_id,
        "dimension_code": dimension_code,
        "gaps": gaps,
        "count": len(gaps),
    }
