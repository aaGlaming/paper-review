"""账号体系的两张表：用户与权限。

字段按 Phase-3 计划 §4.1：
- `user`：user_id、username、email、password_hash、display_name、role、status、
  created_at、last_login_at。`user` 是 MySQL 保留字，表名照 `constraint` 的先例
  用 quoted_name 固定加引号。
- `permission`：permission_id、user_id、permission、resource、granted_at、granted_by；
  外键指向 `user.user_id`，UNIQUE(user_id, permission, resource)。

照 `report/models.py` 的结构：模块自己的 `AuthBase(DeclarativeBase)` +
`create_auth_schema(engine=None)`，不碰别家的 metadata，不引入 alembic。
建表只在显式调用时发生，不塞进应用启动钩子。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import quoted_name


def utc_now() -> datetime:
    """创建时间按 UTC 存，去掉时区信息，避免不同驱动对带时区时间的处理差异。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthBase(DeclarativeBase):
    """账号体系自己的 metadata：create_all 只建 user 与 permission。"""


class User(AuthBase):
    __tablename__ = quoted_name("user", True)

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="student")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Permission(AuthBase):
    __tablename__ = "permission"
    __table_args__ = (
        UniqueConstraint("user_id", "permission", "resource", name="uk_user_permission"),
    )

    permission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    granted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    granted_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")


def create_auth_schema(engine: Engine | None = None) -> None:
    """幂等建账号表。engine 缺省时复用 importing.db 的引擎（只读导入，不修改）。"""
    if engine is None:
        from ..importing import db

        engine = db.get_engine()
    AuthBase.metadata.create_all(engine)
