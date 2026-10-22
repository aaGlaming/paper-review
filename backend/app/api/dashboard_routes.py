"""Teacher-only read endpoints for the dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth.deps import require_permission
from ..auth.permissions import PERM_DASHBOARD
from ..report import dashboard
from .routes import get_session

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(
    _user: dict[str, Any] = Depends(require_permission(PERM_DASHBOARD)),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return dashboard.get_summary(session)


@router.get("/trend")
def trend(
    days: int = Query(default=30, ge=1, le=365),
    _user: dict[str, Any] = Depends(require_permission(PERM_DASHBOARD)),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return dashboard.get_trend(session, days)

