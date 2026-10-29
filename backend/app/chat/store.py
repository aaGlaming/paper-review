"""聊天会话和消息的数据访问；权限及审计由路由层负责。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .models import ChatMessage, ChatSession


def new_session_id() -> str:
    return uuid.uuid4().hex


def new_message_id() -> str:
    return uuid.uuid4().hex


def create_session(session: Session, user_id: str, title: str = "") -> ChatSession:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = ChatSession(session_id=new_session_id(), user_id=user_id, title=title, created_at=now, updated_at=now)
    session.add(row)
    session.flush()
    return row


def list_sessions(session: Session, user_id: str) -> list[ChatSession]:
    return list(session.scalars(
        select(ChatSession).where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.session_id.asc())
    ).all())


def find_session(session: Session, session_id: str) -> ChatSession | None:
    return session.get(ChatSession, session_id)


def delete_session(session: Session, session_id: str) -> None:
    session.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    session.execute(delete(ChatSession).where(ChatSession.session_id == session_id))


def append_message(
    session: Session,
    session_id: str,
    role: str,
    content: str,
    refs: list[dict[str, str]] | None = None,
    model_name: str = "",
) -> ChatMessage:
    """按会话分配 max(seq)+1；并发可能重复，不设唯一约束以免写入失败。

    重复序号由 message_id 最终排序兜底，与旧行为等价。
    """
    if role not in {"user", "assistant"}:
        raise ValueError("role must be user or assistant")
    seq = int(session.scalar(
        select(func.coalesce(func.max(ChatMessage.seq), 0) + 1)
        .where(ChatMessage.session_id == session_id)
    ))
    row = ChatMessage(
        message_id=new_message_id(), session_id=session_id, role=role, content=content,
        refs=refs, model_name=model_name, seq=seq,
    )
    session.add(row)
    session.flush()
    return row


def load_messages(session: Session, session_id: str) -> list[ChatMessage]:
    return list(session.scalars(
        select(ChatMessage).where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.seq.asc(), ChatMessage.message_id.asc())
    ).all())


def touch_session(session: Session, session_id: str) -> None:
    session.execute(
        update(ChatSession).where(ChatSession.session_id == session_id)
        .values(updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
    )
