"""Paginated review overview shared by teacher and student clients."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.deps import require_user
from ..auth.models import User
from ..auth.permissions import PERM_READ_ALL
from ..observability.logging import log_event
from ..report.models import Review, ReviewDimension
from .pagination import clamp_page_size, page_offset
from .routes import get_session

router = APIRouter(prefix="/api")


@router.get("/reviews")
def list_reviews(
    contest_id: str | None = None,
    user_id: str | None = None,
    owner: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
    user: dict[str, Any] = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List reviews with server-enforced ownership and batched summaries."""
    permissions = user.get("permissions") or []
    can_read_all = PERM_READ_ALL in permissions
    viewer_id = user["user_id"]
    size = clamp_page_size(page_size)

    filters = []
    if can_read_all:
        if user_id is not None:
            filters.append(Review.user_id.is_(None) if user_id == "" else Review.user_id == user_id)
        if owner == "owned":
            filters.append(Review.user_id.is_not(None))
        elif owner == "orphan":
            filters.append(Review.user_id.is_(None))
    else:
        filters.append(Review.user_id == viewer_id)
    if contest_id is not None:
        filters.append(Review.contest_id == contest_id)

    total = session.scalar(select(func.count()).select_from(Review).where(*filters)) or 0
    rows = list(
        session.execute(
            select(Review, User.username)
            .outerjoin(User, Review.user_id == User.user_id)
            .where(*filters)
            .order_by(Review.created_at.desc(), Review.review_id.asc())
            .offset(page_offset(page, size))
            .limit(size)
        ).all()
    )

    review_ids = [row.review_id for row, _ in rows]
    bands_by_review: dict[str, dict[str, str | None]] = defaultdict(dict)
    if review_ids:
        dimensions = session.execute(
            select(ReviewDimension.review_id, ReviewDimension.dimension_code, ReviewDimension.band)
            .where(ReviewDimension.review_id.in_(review_ids))
        ).all()
        for review_id, dimension_code, band in dimensions:
            bands_by_review[review_id][dimension_code] = band

    reviews = []
    others = 0
    for row, owner_username in rows:
        is_other = row.user_id != viewer_id
        if is_other:
            others += 1
        changes = row.change_list or []
        reviews.append(
            {
                "review_id": row.review_id,
                "contest_id": row.contest_id,
                "rubric_id": row.rubric_id,
                "rubric_version": row.rubric_version,
                "model_name": row.model_name,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "user_id": row.user_id,
                "owner_username": owner_username,
                "bands": bands_by_review[row.review_id],
                "finding_total": sum(
                    1 for item in changes if isinstance(item, dict) and "finding_kind" in item
                ),
            }
        )

    scope = "all" if can_read_all else "own"
    if can_read_all and others:
        log_event(
            "audit", "records_listed", viewer_id=viewer_id,
            returned=len(reviews), others=others, scope=scope,
        )
    return {"reviews": reviews, "total": total, "page": page, "page_size": size, "scope": scope}
