from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class AgentTraceBase(DeclarativeBase):
    pass


class AgentStep(AgentTraceBase):
    __tablename__ = "agent_step"
    __table_args__ = (UniqueConstraint("review_id", "idx", name="uk_review_idx"),)

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    args_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    result_note: Mapped[str] = mapped_column(String(256), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_agent_trace_schema(engine=None) -> None:
    if engine is None:
        from ..importing.db import get_engine

        engine = get_engine()
    AgentTraceBase.metadata.create_all(engine)


def digest_args(args: dict) -> str:
    payload = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def _as_dict(row: AgentStep) -> dict[str, Any]:
    return {
        "step_id": row.step_id,
        "review_id": row.review_id,
        "idx": row.idx,
        "node": row.node,
        "action": row.action,
        "args_digest": row.args_digest,
        "result_note": row.result_note,
        "ok": row.ok,
        "error_code": row.error_code,
        "elapsed_ms": row.elapsed_ms,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def append_step(*, review_id, node, action, args_digest, result_note, ok,
                error_code=None, elapsed_ms=0, session=None) -> dict:
    def _insert(db_session: Session) -> dict:
        for attempt in range(2):
            current = db_session.scalar(
                select(func.max(AgentStep.idx)).where(AgentStep.review_id == review_id)
            ) or 0
            row = AgentStep(
                step_id=uuid.uuid4().hex,
                review_id=review_id,
                idx=int(current) + 1,
                node=node,
                action=action,
                args_digest=str(args_digest),
                result_note=str(result_note)[:256],
                ok=bool(ok),
                error_code=error_code,
                elapsed_ms=int(elapsed_ms),
                created_at=_now(),
            )
            db_session.add(row)
            try:
                db_session.flush()
                return _as_dict(row)
            except IntegrityError:
                db_session.rollback()
                if attempt == 1:
                    raise
        raise RuntimeError("agent step insert failed")

    if session is not None:
        return _insert(session)
    from ..importing.db import session_scope

    with session_scope() as db_session:
        return _insert(db_session)


def load_steps(review_id: str, *, session=None) -> list[dict]:
    def _load(db_session: Session) -> list[dict]:
        rows = db_session.scalars(
            select(AgentStep).where(AgentStep.review_id == review_id).order_by(AgentStep.idx.asc())
        ).all()
        return [_as_dict(row) for row in rows]

    if session is not None:
        try:
            return _load(session)
        except OperationalError:
            return []
    from ..importing.db import session_scope

    try:
        with session_scope() as db_session:
            return _load(db_session)
    except OperationalError:
        return []


def record_call(*, review_id, action, args, result, elapsed_ms, node="tools", session=None) -> dict:
    ok = bool(result.get("ok")) if isinstance(result, dict) else False
    error_code = result.get("error_code") if isinstance(result, dict) else "not_allowed"
    if ok:
        data = result.get("data")
        note = f"命中 {len(data)} 条" if isinstance(data, list) else "ok"
    else:
        message = str(result.get("message") or "")[:80] if isinstance(result, dict) else ""
        note = f"{error_code or 'not_allowed'}: {message}"[:256]
    return append_step(
        review_id=review_id,
        node=node,
        action=action,
        args_digest=digest_args(args),
        result_note=note,
        ok=ok,
        error_code=error_code,
        elapsed_ms=elapsed_ms,
        session=session,
    )
