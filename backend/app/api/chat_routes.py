"""AI 问询会话 API：能力权限由 chat:use 控制，会话按发起人隔离。"""

from __future__ import annotations

import json
import os
import time
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.deps import require_permission
from ..auth.permissions import PERM_CHAT
from ..chat import answering, retrieval
from ..chat import analytics
from ..chat import store as chat_store
from ..chat.models import ChatMessage, ChatSession
from ..observability.logging import log_event
from .routes import get_session

router = APIRouter(prefix="/api/chat")
_NOT_FOUND = "找不到问询会话"


class CreateSessionRequest(BaseModel):
    title: str = ""


class AnswerRequest(BaseModel):
    question: str | None = None
    contest_id: str | None = None


class AnalyticsRequest(BaseModel):
    contest_id: str | None = None
    kind: str | None = None
    dimension_code: str | None = None


class SummaryRequest(BaseModel):
    contest_id: str | None = None
    top: int = 5
    session_id: str | None = None


def get_search_fn():
    return retrieval.search_records


def get_chat_fn():
    return None


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _owned_session(session: Session, session_id: str, user_id: str) -> ChatSession:
    row = chat_store.find_session(session, session_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return row


@router.get("/sessions")
def get_sessions(
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(require_permission(PERM_CHAT)),
) -> dict[str, Any]:
    rows = chat_store.list_sessions(session, user["user_id"])
    ids = [row.session_id for row in rows]
    counts: dict[str, int] = {}
    if ids:
        counts = dict(session.execute(
            select(ChatMessage.session_id, func.count(ChatMessage.message_id))
            .where(ChatMessage.session_id.in_(ids))
            .group_by(ChatMessage.session_id)
        ).all())
    return {"sessions": [
        {
            "session_id": row.session_id, "title": row.title,
            "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at),
            "message_count": counts.get(row.session_id, 0),
        }
        for row in rows
    ]}


@router.post("/sessions", status_code=201)
def post_session(
    body: CreateSessionRequest | None = None,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(require_permission(PERM_CHAT)),
) -> dict[str, Any]:
    title = (body.title if body else "").strip()[:256] or "新会话"
    row = chat_store.create_session(session, user["user_id"], title)
    log_event("ai_chat", "session_created", session_id=row.session_id, user_id=user["user_id"])
    return {"session_id": row.session_id, "title": row.title, "created_at": _iso(row.created_at)}


@router.delete("/sessions/{session_id}", status_code=204)
def remove_session(
    session_id: str,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(require_permission(PERM_CHAT)),
) -> Response:
    _owned_session(session, session_id, user["user_id"])
    message_count = session.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
    ) or 0
    chat_store.delete_session(session, session_id)
    log_event(
        "ai_chat", "session_deleted", session_id=session_id,
        user_id=user["user_id"], messages=int(message_count),
    )
    return Response(status_code=204)


@router.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(require_permission(PERM_CHAT)),
) -> dict[str, Any]:
    _owned_session(session, session_id, user["user_id"])
    messages = chat_store.load_messages(session, session_id)
    log_event(
        "ai_chat", "messages_read", session_id=session_id,
        user_id=user["user_id"], count=len(messages),
    )
    return {"session_id": session_id, "messages": [
        {
            "message_id": row.message_id, "role": row.role, "content": row.content,
            "refs": row.refs, "model_name": row.model_name, "created_at": _iso(row.created_at),
        }
        for row in messages
    ]}


@router.post("/sessions/{session_id}/messages")
def post_answer(
    session_id: str,
    body: AnswerRequest,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(require_permission(PERM_CHAT)),
    search_fn=Depends(get_search_fn),
    chat_fn=Depends(get_chat_fn),
) -> dict[str, Any]:
    owner = _owned_session(session, session_id, user["user_id"])
    question = (body.question or "").strip()
    if not question:
        log_event("ai_chat", "chat_failed", session_id=session_id,
                  user_id=user["user_id"], reason="empty_question")
        raise HTTPException(status_code=400, detail="问题不能为空")
    if len(question) > 2000:
        raise HTTPException(status_code=400, detail="问题不能超过 2000 字")
    contest_id = (body.contest_id or "").strip()
    if not contest_id:
        raise HTTPException(status_code=400, detail="缺少赛题范围")

    started = time.perf_counter()
    try:
        result = answering.answer_question(
            session, session_row=owner, question=question, contest_id=contest_id,
            search_fn=search_fn, chat_fn=chat_fn,
        )
    except answering.AnswerError as exc:
        log_event("ai_chat", "chat_failed", session_id=session_id,
                  user_id=user["user_id"], reason=answering.failure_reason(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    user_message = chat_store.append_message(session, session_id, "user", question)
    assistant_message = chat_store.append_message(
        session, session_id, "assistant", result["content"],
        refs=result["refs"], model_name=result["model_name"],
    )
    # MySQL DATETIME 默认精度为秒；为同轮 user/assistant 消息建立可读的确定顺序。
    assistant_message.created_at = max(
        assistant_message.created_at, user_message.created_at + timedelta(seconds=1)
    )
    chat_store.touch_session(session, session_id)
    notes = result["notes"]
    log_event(
        "ai_chat", "chat_answered", session_id=session_id, user_id=user["user_id"],
        question_chars=len(question), retrieved=notes["retrieved"], cited=len(result["refs"]),
        rejected=len(notes["rejected"]), unused=notes["unused"],
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
    return {
        "message_id": assistant_message.message_id,
        "content": result["content"], "refs": result["refs"],
        "model_name": result["model_name"],
        "notifications": {"rejected": len(notes["rejected"]), "unused": notes["unused"]},
    }


@router.post("/analytics")
def post_analytics(
    body: AnalyticsRequest,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(require_permission(PERM_CHAT)),
) -> dict[str, Any]:
    contest_id = (body.contest_id or "").strip()
    if not contest_id:
        raise HTTPException(status_code=400, detail="缺少赛题范围")
    handlers = {
        "bands": lambda: analytics.compare_bands(session, contest_id=contest_id),
        "conflicts": lambda: analytics.summarize_conflicts(session, contest_id=contest_id),
        "gaps": lambda: analytics.evidence_gaps(
            session, contest_id=contest_id, dimension_code=body.dimension_code
        ),
    }
    if body.kind not in handlers:
        raise HTTPException(status_code=400, detail="问询统计类型无效")
    started = time.perf_counter()
    try:
        result = handlers[body.kind]()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rows = len(result.get({"bands": "bands", "conflicts": "hotspots", "gaps": "gaps"}[body.kind], []))
    log_event(
        "ai_chat", "analytics_run", user_id=user["user_id"], contest_id=contest_id,
        kind=body.kind, elapsed_ms=int((time.perf_counter() - started) * 1000), rows=rows,
    )
    return {"kind": body.kind, "result": result}


_SUMMARY_SYSTEM_PROMPT = (
    "你是教研摘要助手。只能使用下面给出的统计数字与记录引用；不得新增任何数字；"
    "不得输出奖项、名次、获奖概率；用中文回答，控制在 300 字以内，先给结论再给依据。"
)


@router.post("/summary")
def post_summary(
    body: SummaryRequest,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(require_permission(PERM_CHAT)),
    search_fn=Depends(get_search_fn),
    chat_fn=Depends(get_chat_fn),
) -> dict[str, Any]:
    contest_id = (body.contest_id or "").strip()
    if not contest_id:
        raise HTTPException(status_code=400, detail="缺少赛题范围")
    if body.session_id:
        _owned_session(session, body.session_id, user["user_id"])

    started = time.perf_counter()
    try:
        statistics = {
            "bands": analytics.compare_bands(session, contest_id=contest_id),
            "conflicts": analytics.summarize_conflicts(
                session, contest_id=contest_id, top=body.top
            ),
            "gaps": analytics.evidence_gaps(session, contest_id=contest_id),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    available = list(search_fn(
        "教研摘要证据", contest_id=contest_id, limit=8
    ) or [])[:8]
    references = [
        {"review_id": str(item.get("review_id", "")),
         "dimension_code": str(item.get("dimension_code", ""))}
        for item in available
    ]
    prompt = "\n".join((
        "【统计】" + json.dumps(statistics, ensure_ascii=False, separators=(",", ":")),
        "【可用引用】" + json.dumps(references, ensure_ascii=False, separators=(",", ":")),
        "【任务】写一段给教研会用的情况摘要，并在结尾用 "
        "[review_id=xxx dim=yyy] 标注至少 3 条证据。",
    ))
    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    try:
        content = answering.call_chat_with_retry(messages, chat_fn)
    except answering.AnswerError as exc:
        log_event(
            "ai_chat", "chat_failed", session_id=body.session_id or "",
            user_id=user["user_id"], reason=answering.failure_reason(exc),
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    content, refs, rejected, _unused = answering.validate_citations(content, references)
    notes: dict[str, Any] = {"rejected": len(rejected)}
    if len(refs) < 3:
        notes["evidence_short"] = len(refs)
        content += f"（可用证据不足 3 条，已如实标注 {len(refs)} 条）"
    if body.session_id:
        assistant_message = chat_store.append_message(
            session, body.session_id, "assistant", content,
            refs=refs, model_name=os.environ.get("LLM_MODEL", "").strip(),
        )
        # 响应不需要消息 ID；显式保留实例以确保 INSERT 在同一事务完成。
        del assistant_message
        chat_store.touch_session(session, body.session_id)
    log_event(
        "ai_chat", "summary_generated", user_id=user["user_id"], contest_id=contest_id,
        refs=len(refs), rejected=len(rejected), evidence_short=notes.get("evidence_short", 0),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
    return {
        "content": content, "refs": refs,
        "model_name": os.environ.get("LLM_MODEL", "").strip(), "notes": notes,
    }
