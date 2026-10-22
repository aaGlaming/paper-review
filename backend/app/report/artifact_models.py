"""Structured review artifacts and their idempotent schema migration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import nullcontext
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from .models import ReportBase

ARTIFACT_TYPES = ("claim", "table", "citation")


class ReviewArtifact(ReportBase):
    __tablename__ = "review_artifact"
    __table_args__ = (
        UniqueConstraint("review_id", "ordinal", name="uq_review_artifact_review_ordinal"),
        CheckConstraint("ordinal >= 0", name="ck_review_artifact_ordinal_nonnegative"),
        CheckConstraint("char_start >= 0 AND char_end > char_start", name="ck_review_artifact_span"),
        Index("ix_review_artifact_review_ordinal", "review_id", "ordinal"),
    )

    artifact_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("review.review_id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(16), nullable=False)
    section_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_text: Mapped[str | None] = mapped_column(Text, nullable=True)


def create_artifact_schema(engine: Engine | None = None) -> None:
    """Create only review_artifact if absent; safe to call repeatedly."""
    if engine is None:
        from ..importing import db

        engine = db.get_engine()
    if not inspect(engine).has_table("review_artifact"):
        ReportBase.metadata.create_all(engine, tables=[ReviewArtifact.__table__], checkfirst=True)


def save_artifacts(
    review_id: str,
    items: Sequence[Mapping[str, Any]],
    session: Session | None = None,
) -> list[ReviewArtifact]:
    """Validate and stage artifacts for one review.

    Required fields by type are `claim_text` for claim, `table_markdown` for
    table, and `citation_text` for citation. Every item also requires a known
    type, unique non-negative ordinal, and a non-empty half-open source span.
    The caller owns commit/rollback when a session is supplied; without one,
    this function uses the standard report database transaction.
    """
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ValueError("items 必须是产物列表")
    normalized: list[dict[str, Any]] = []
    seen_ordinals: set[int] = set()
    required_fields = {"claim": "claim_text", "table": "table_markdown", "citation": "citation_text"}
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"第 {index + 1} 条产物必须是对象")
        artifact_type = item.get("artifact_type")
        if artifact_type not in ARTIFACT_TYPES:
            raise ValueError(f"artifact_type 必须是以下类型之一：{', '.join(ARTIFACT_TYPES)}")
        ordinal = item.get("ordinal")
        start, end = item.get("char_start"), item.get("char_end")
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
            raise ValueError("ordinal 必须是非负整数")
        if ordinal in seen_ordinals:
            raise ValueError(f"ordinal 重复：{ordinal}")
        seen_ordinals.add(ordinal)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (start, end)):
            raise ValueError("char_start 和 char_end 必须是整数")
        if start < 0 or end <= start:
            raise ValueError("原文区间必须满足 0 <= char_start < char_end")
        field = required_fields[artifact_type]
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{artifact_type} 产物缺少非空字段 {field}")
        normalized.append(
            {
                "review_id": review_id,
                "artifact_type": artifact_type,
                "ordinal": ordinal,
                "char_start": start,
                "char_end": end,
                "section_type": item.get("section_type"),
                "claim_text": item.get("claim_text") if artifact_type == "claim" else None,
                "table_markdown": item.get("table_markdown") if artifact_type == "table" else None,
                "citation_text": item.get("citation_text") if artifact_type == "citation" else None,
            }
        )

    if session is None:
        from ..importing.db import session_scope

        context = session_scope()
    else:
        context = nullcontext(session)
    with context as work:
        rows = [ReviewArtifact(**item) for item in normalized]
        work.add_all(rows)
        work.flush()
        return rows
