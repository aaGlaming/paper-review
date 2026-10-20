"""用户管理接口：列表（仅教师）与详情（本人或教师）。

防枚举：详情接口对「别人的 id」返回 404 而不是 403——403 等于告诉调用方
「这个 id 存在，只是不给你看」。列表接口才用 403（计划 §4.6 判据 3）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from ..auth import store as auth_store
from ..auth.deps import current_user, require_permission
from ..auth.models import User
from ..auth.permissions import PERM_READ_ALL
from ..report.models import Review, ReviewSession
from .pagination import clamp_page_size, page_offset

router = APIRouter(prefix="/api/users")

# 固定文案：不带 user_id，否则「别人的 id」与「不存在的 id」返回体不同，
# 调用方可借此区分存在性（枚举用户）。
_NOT_FOUND = "找不到用户"


def mask_email(email: str) -> str:
    """邮箱打码：abc@example.com → a***@example.com（首字符 + *** + @域名）。"""
    local, sep, domain = str(email or "").partition("@")
    if not sep or not domain:
        return "***"
    head = local[:1] if local else "*"
    return f"{head}***@{domain}"


def _public_row(row: User) -> dict[str, Any]:
    return {
        "user_id": row.user_id,
        "username": row.username,
        "display_name": row.display_name,
        "role": row.role,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
        "email_masked": mask_email(row.email),
    }


@router.get("", dependencies=[Depends(require_permission(PERM_READ_ALL))])
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
) -> dict[str, Any]:
    """用户列表：created_at 倒序，同秒按 user_id 升序；page_size 静默夹到 100。"""
    size = clamp_page_size(page_size)
    with auth_store.session_scope_cm() as session:
        total = session.scalar(select(func.count()).select_from(User)) or 0
        rows = list(
            session.scalars(
                select(User)
                .order_by(User.created_at.desc(), User.user_id.asc())
                .offset(page_offset(page, size))
                .limit(size)
            ).all()
        )
        return {
            "users": [_public_row(row) for row in rows],
            "total": total,
            "page": int(page),
            "page_size": size,
        }


@router.get("/{user_id}")
def get_user(user_id: str, me: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """用户详情：本人 200；非本人需 PERM_READ_ALL，否则 404（防枚举）。

    响应里不出现 password_hash；reviews 取该用户最近 20 条评审。
    """
    target = str(user_id or "")
    if target != me["user_id"] and PERM_READ_ALL not in (me.get("permissions") or []):
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    with auth_store.session_scope_cm() as session:
        row = auth_store.find_user_by_id(session, target)
        if row is None:
            raise HTTPException(status_code=404, detail=_NOT_FOUND)
        permissions = auth_store.list_permissions(session, row.user_id)
        reviews = _recent_reviews(session, row.user_id)
        return {
            "user_id": row.user_id,
            "username": row.username,
            "display_name": row.display_name,
            "role": row.role,
            "status": row.status,
            "email": row.email,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
            "permissions": permissions,
            "reviews": reviews,
        }


def _recent_reviews(session: Any, user_id: str) -> list[dict[str, Any]]:
    # review 表没有 status 列（状态在 review_session 快照里），无快照则为 None。
    rows = list(
        session.scalars(
            select(Review)
            .where(Review.user_id == user_id)
            .order_by(Review.created_at.desc(), Review.review_id.asc())
            .limit(20)
        ).all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        snapshot = session.get(ReviewSession, row.review_id)
        out.append(
            {
                "review_id": row.review_id,
                "contest_id": row.contest_id,
                "status": snapshot.status if snapshot is not None else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return out
