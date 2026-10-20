"""AI 问询会话与消息表；建表只由显式 create_chat_schema 调用。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ChatBase(DeclarativeBase):
    """聊天模块独立 metadata，不隐式改动其他模块的 schema。"""


class ChatSession(ChatBase):
    __tablename__ = "chat_session"
    __table_args__ = (Index("ix_chat_session_user_updated", "user_id", "updated_at"),)

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class ChatMessage(ChatBase):
    __tablename__ = "chat_message"
    __table_args__ = (Index("ix_chat_message_session_created", "session_id", "created_at"),)

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("chat_session.session_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # v3.3.1 起写入 `[{review_id, dimension_code}]`，v3.3.0 恒为 null。
    refs: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


def create_chat_schema(engine: Engine | None = None) -> None:
    """幂等建聊天表；应用启动不会隐式调用本函数。"""
    if engine is None:
        from ..importing.db import get_engine

        engine = get_engine()
    ChatBase.metadata.create_all(engine)
