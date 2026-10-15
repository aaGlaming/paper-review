"""评审记录的两张表。

字段按开发计划书第七节 7.2：
- `review`：review_id、contest_id、rubric_id、rubric_version、model_name、created_at
- `review_dimension`：review_id、dimension_code、band、chunk_ids、quote、status

本版允许修改范围不含 `backend/app/importing/`，所以照 `backend/app/retrieve/models.py` 的先例，
在这里定义自己的 `ReportBase`；建表用 `metadata.create_all()`，只建这两张表，不碰赛题那七张表，
也不碰 `paper_parent`。连接复用 `importing.db` 的引擎与会话工厂（只读导入，不修改）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """创建时间按 UTC 存，去掉时区信息，避免不同驱动对带时区时间的处理差异。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReportBase(DeclarativeBase):
    """评审记录自己的 metadata：create_all 只建 review 与 review_dimension。"""


class Review(ReportBase):
    __tablename__ = "review"

    review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contest_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    rubric_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    rubric_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class ReviewDimension(ReportBase):
    __tablename__ = "review_dimension"

    review_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("review.review_id", ondelete="CASCADE"), primary_key=True
    )
    dimension_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    chunk_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)


def create_report_schema(engine: Engine | None = None) -> None:
    """建评审记录两张表。表已存在时是空操作。"""
    if engine is None:
        from ..importing import db

        engine = db.get_engine()
    ReportBase.metadata.create_all(engine)
