"""父块全文的 ORM 模型。

本版允许修改范围不含 `backend/app/importing/`，所以 `paper_parent` 的表模型与仓储放在本目录，
只**只读导入** `backend/app/importing/db.py` 的引擎与会话工厂来共用连接，不修改那个文件。
建表用 `metadata.create_all()`，不引入 alembic，不引入锁定清单之外的依赖。

字段按开发计划书第七节：parent_id、review_id、section_type、content、char_span。
`section_type` 是单值字符串；父块全文只落在 MySQL，不进 Chroma。
"""

from __future__ import annotations

from sqlalchemy import JSON, String, Text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ParentBase(DeclarativeBase):
    """父块表自己的 metadata：create_all 只建 paper_parent，不碰赛题那七张表。"""


class PaperParent(ParentBase):
    __tablename__ = "paper_parent"

    parent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    section_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_span: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)


def create_parent_schema(engine: Engine | None = None) -> None:
    """建父块表。表已存在时是空操作。"""
    if engine is None:
        from ..importing import db

        engine = db.get_engine()
    ParentBase.metadata.create_all(engine)
