"""鉴权依赖：`current_user` 从 Bearer token 取身份。

流程：取 Bearer → decode_token → 查库 → status 必须是 active →
返回 {user_id, username, role, permissions}。

失败一律 401，文案统一「未登录或登录已过期」，不区分缺 token / 签名错 /
过期 / 用户不存在 / 被停用。日志里才写具体 reason。

`require_permission` 失败走 403 + audit/permission_denied，与 401 的
auth/token_rejected 不混：没登录是 auth，登录了但没权限是 audit。

依赖可被 override（FastAPI 的 dependency_overrides），测试里会用到。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..observability.logging import log_event
from . import store as _store
from .token import TokenError, decode_token, password_fingerprint

_UNAUTHORIZED = "未登录或登录已过期"
_FORBIDDEN = "没有权限执行该操作"


def get_auth_session() -> Any:
    """每个请求一个账号会话。单独函数以便测试 override。"""
    with _store.session_scope() as session:
        yield session


def current_user(authorization: str | None = Header(None)) -> dict[str, Any]:
    """从 Authorization 头解析当前用户。失败一律 401 统一文案。"""
    user = _resolve(authorization)
    if user is None:
        _reject("missing_token")
    return user


def _resolve(authorization: str | None) -> dict[str, Any] | None:
    """公共解析：无有效 Bearer 返回 None，有头则校验（坏头直接 401）。"""
    scheme, _, credentials = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        return None
    try:
        payload = decode_token(credentials.strip())
    except TokenError as exc:
        _reject(str(exc.reason))
    return _load_user(payload)


def _load_user(payload: dict[str, Any]) -> dict[str, Any]:
    with _store.session_scope_cm() as session:
        row = _store.find_user_by_id(session, str(payload.get("uid") or ""))
        if row is None:
            _reject("unknown_user")
        if row.status != "active":
            _reject("disabled")
        if password_fingerprint(row.password_hash) != str(payload.get("pv") or ""):
            _reject("pv_mismatch")
        return {
            "user_id": row.user_id,
            "username": row.username,
            "role": row.role,
            "permissions": _store.list_permissions(session, row.user_id),
        }


def _reject(reason: str) -> None:
    log_event("auth", "token_rejected", reason=reason)
    raise HTTPException(status_code=401, detail=_UNAUTHORIZED)


def require_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """别名依赖：写法上区分「要登录」与「要取身份」。"""
    return user


def require_permission(code: str) -> Callable[..., dict[str, Any]]:
    """权限门卫工厂：permissions 含 code 才放行，否则 403 + audit 日志。

    403 文案统一，不透露需要哪个权限。失败日志进 audit（登录了但没权限），
    与 401 的 auth/token_rejected 不混。
    """

    def _guard(*, user: dict[str, Any] = Depends(current_user), request: Request) -> dict[str, Any]:
        if code in (user.get("permissions") or []):
            return user
        log_event(
            "audit", "permission_denied",
            user_id=user.get("user_id"), required=code,
            path=request.url.path if request is not None else "",
        )
        raise HTTPException(status_code=403, detail=_FORBIDDEN)

    return _guard


def require_any_permission(*codes: str) -> Callable[..., dict[str, Any]]:
    """多权限门卫：含任一即放行，否则 403 + audit 日志。"""

    def _guard(*, user: dict[str, Any] = Depends(current_user), request: Request) -> dict[str, Any]:
        owned = set(user.get("permissions") or [])
        for code in codes:
            if code in owned:
                return user
        log_event(
            "audit", "permission_denied",
            user_id=user.get("user_id"), required="|".join(codes),
            path=request.url.path if request is not None else "",
        )
        raise HTTPException(status_code=403, detail=_FORBIDDEN)

    return _guard
