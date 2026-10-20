"""账号数据访问：会话工厂与用户/权限读写。

连接复用 `importing.db` 的引擎（只读导入，不修改），照 `report/store.py` 的写法。
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .models import Permission, User, create_auth_schema
from .permissions import DEFAULT_PERMISSIONS


def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """每个请求一个会话：成功提交，出错回滚。"""
    if engine is None:
        from ..importing import db

        engine = db.get_engine()
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


session_scope = contextmanager(session_scope)


@contextmanager
def session_scope_cm(engine: Engine | None = None) -> Iterator[Session]:
    """别名：与 session_scope 同义，接口层用这个名字。"""
    with session_scope(engine) as session:
        yield session


def new_user_id() -> str:
    return uuid.uuid4().hex


def find_user_by_username(session: Session, username: str) -> User | None:
    return session.scalars(select(User).where(User.username == username)).first()


def find_user_by_email(session: Session, email: str) -> User | None:
    return session.scalars(select(User).where(User.email == email)).first()


def find_user_by_id(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def create_user(
    session: Session,
    *,
    username: str,
    email: str,
    password_hash: str,
    display_name: str = "",
    role: str = "student",
) -> User:
    """建用户并按 role 写默认权限集。调用方已做唯一性检查。"""
    row = User(
        user_id=new_user_id(),
        username=username,
        email=email,
        password_hash=password_hash,
        display_name=display_name,
        role=role,
        status="active",
    )
    session.add(row)
    session.flush()
    for permission in DEFAULT_PERMISSIONS.get(role, DEFAULT_PERMISSIONS["student"]):
        session.add(
            Permission(
                permission_id=uuid.uuid4().hex,
                user_id=row.user_id,
                permission=permission,
                resource="",
            )
        )
    session.flush()
    return row


def list_permissions(session: Session, user_id: str) -> list[str]:
    rows = session.scalars(select(Permission).where(Permission.user_id == user_id)).all()
    return sorted({row.permission for row in rows})


def touch_login(session: Session, row: User) -> None:
    from .models import utc_now

    row.last_login_at = utc_now()
    session.flush()


__all__: list[str] = [
    "create_auth_schema",
    "create_user",
    "find_user_by_email",
    "find_user_by_id",
    "find_user_by_username",
    "list_permissions",
    "new_user_id",
    "session_scope",
    "touch_login",
]
