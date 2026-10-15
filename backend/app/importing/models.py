"""赛题目录的数据层模型。

只建赛题与量规相关的七张表，字段以开发计划书第七节为准：
contest、constraint、rubric_template、rubric、dimension、pitfall、exemplar。
paper_parent、sample_paper、review、review_dimension 留给后续版本，本版不建。

建表一律用 `Base.metadata.create_all()`：alembic 不在锁定依赖内，本版不引入迁移工具。
`constraint` 是 MySQL 保留字，表名用 quoted_name 固定加引号，避免手工写 SQL 时踩语法错误。
`section_types` 在开发计划书里只列在 constraint 上，这里按数据包的真实字段同步给 dimension 与 pitfall
（量规的 section_types 用来收窄检索范围，扣分点的 section_types 用来指明常见章节）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import quoted_name


class Base(DeclarativeBase):
    pass


class Contest(Base):
    __tablename__ = "contest"

    contest_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    problem_code: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)


class Constraint(Base):
    __tablename__ = quoted_name("constraint", True)

    constraint_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contest_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("contest.contest_id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    check_type: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    section_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class RubricTemplate(Base):
    __tablename__ = "rubric_template"

    template_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Rubric(Base):
    __tablename__ = "rubric"

    rubric_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contest_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("contest.contest_id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    source_template_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("rubric_template.template_id"), nullable=True
    )


class Dimension(Base):
    __tablename__ = "dimension"
    __table_args__ = (UniqueConstraint("rubric_id", "code", name="uq_dimension_rubric_code"),)

    dimension_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rubric_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("rubric.rubric_id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_prompts: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    section_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    bands: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)


class Pitfall(Base):
    __tablename__ = "pitfall"

    pitfall_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contest_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("contest.contest_id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_code: Mapped[str] = mapped_column(String(32), nullable=False)
    phenomenon: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    section_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class Exemplar(Base):
    __tablename__ = "exemplar"

    exemplar_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contest_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("contest.contest_id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_code: Mapped[str] = mapped_column(String(32), nullable=False)
    band: Mapped[str] = mapped_column(String(16), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
