"""账号接口：注册 / 登录 / 登出 / me。

防枚举三条硬要求：
1. 用户名重复与邮箱重复返回同一句 409，不探出哪个字段重复；
2. 用户名不存在与密码错误返回同一句 401、同状态码、同响应体；
3. 响应里不带 hint 字段。
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..observability.logging import log_event
from ..observability.metrics import inc_auth
from ..auth import store as auth_store
from ..auth.deps import current_user
from ..auth.security import (
    check_email,
    check_password_strength,
    check_username,
    hash_password,
    verify_password,
)
from ..auth.token import issue_token

router = APIRouter(prefix="/api/auth")

_REGISTER_CONFLICT = "该注册信息不可用"
_LOGIN_FAILED = "用户名或密码错误"


class RegisterRequest(BaseModel):
    username: str = ""
    email: str = ""
    password: str = ""
    display_name: str = ""


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


@router.post("/register", status_code=201)
def register(payload: RegisterRequest) -> dict[str, Any]:
    """注册：成功 201；重复 409 统一文案；密码不合规 422。"""
    username = str(payload.username or "").strip()
    email = str(payload.email or "").strip()
    if (reason := check_username(username)) is not None:
        raise HTTPException(status_code=422, detail=reason)
    if (reason := check_email(email)) is not None:
        raise HTTPException(status_code=422, detail=reason)
    if (reason := check_password_strength(payload.password)) is not None:
        raise HTTPException(status_code=422, detail=reason)
    with auth_store.session_scope_cm() as session:
        if auth_store.find_user_by_username(session, username) is not None:
            raise HTTPException(status_code=409, detail=_REGISTER_CONFLICT)
        if auth_store.find_user_by_email(session, email) is not None:
            raise HTTPException(status_code=409, detail=_REGISTER_CONFLICT)
        row = auth_store.create_user(
            session,
            username=username,
            email=email,
            password_hash=hash_password(str(payload.password)),
            display_name=str(payload.display_name or "").strip(),
        )
        log_event("auth", "register", user_id=row.user_id, username=row.username, role=row.role)
        return {"user_id": row.user_id, "username": row.username, "role": row.role}


@router.post("/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    """登录：成功 200 带 token；失败 401 统一文案。"""
    started = time.perf_counter()
    username = str(payload.username or "").strip()
    with auth_store.session_scope_cm() as session:
        row = auth_store.find_user_by_username(session, username)
        if row is None:
            log_event("auth", "login_failed", username=username, reason="not_found")
            inc_auth(False)
            raise HTTPException(status_code=401, detail=_LOGIN_FAILED)
        if row.status != "active":
            log_event("auth", "login_failed", username=username, reason="disabled")
            inc_auth(False)
            raise HTTPException(status_code=401, detail=_LOGIN_FAILED)
        if not verify_password(str(payload.password or ""), row.password_hash):
            log_event("auth", "login_failed", username=username, reason="bad_password")
            inc_auth(False)
            raise HTTPException(status_code=401, detail=_LOGIN_FAILED)
        auth_store.touch_login(session, row)
        token = issue_token(row.user_id, row.role, row.password_hash)
        permissions = auth_store.list_permissions(session, row.user_id)
        log_event(
            "auth", "login_success", user_id=row.user_id, username=row.username,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
        inc_auth(True)
        return {
            "token": token,
            "user_id": row.user_id,
            "role": row.role,
            "permissions": permissions,
        }


@router.post("/logout", status_code=204)
def logout(user: dict[str, Any] = Depends(current_user)) -> Response:
    """登出：只清前端，服务端不撤销 token（改密码即旧 token 全失效，见 token.py）。

    204 无 body。未登录调同样走 current_user 的 401。
    """
    log_event("auth", "logout", user_id=user["user_id"])
    return Response(status_code=204)


@router.get("/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """当前身份：登录有效时 200，否则 401。"""
    return user
