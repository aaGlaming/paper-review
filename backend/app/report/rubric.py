"""只读取数：该赛题当前 published 的那一版量规，以及它的约束。

量规只从**库**里读，不读 `data/contests/` 下的 JSON：报告要反映当时实际用的那一版，
而版本是有演进的（发布新版只影响之后新建的评审单）。

找不到赛题、或该赛题没有已发布量规时返回空表、`rubric_id` 为 `None`，**不抛错**，
也不兜底到别的赛题；约束此时也一并返回空表，因为「无维度可评」时报告里的修改清单必须为空。

本模块只读：不写库、不发 HTTP、不调模型，也不导入检索包。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..importing.models import Constraint, Dimension, Rubric

PUBLISHED = "published"


@contextmanager
def _session(session: Session | None) -> Iterator[Session]:
    """有外部会话就用它（不提交，由调用方决定），否则自己开一个。"""
    if session is not None:
        yield session
        return
    from ..importing import db

    with db.session_scope() as owned:
        yield owned


def _empty_inputs() -> dict[str, Any]:
    return {"rubric_id": None, "rubric_version": None, "dimensions": [], "constraints": []}


def load_review_inputs(contest_id: str | None, *, session: Session | None = None) -> dict[str, Any]:
    """按赛题取该题当前已发布量规的维度与约束；取不到就返回空表。"""
    name = str(contest_id or "").strip()
    if not name:
        return _empty_inputs()

    with _session(session) as work:
        chosen = work.scalars(
            select(Rubric)
            .where(Rubric.contest_id == name, Rubric.status == PUBLISHED)
            .order_by(Rubric.version.desc())
        ).first()
        if chosen is None:
            return _empty_inputs()

        dimensions = [
            {
                "dimension_code": one.code,
                "name": one.name,
                "weight": int(one.weight),
                "section_types": [str(item) for item in (one.section_types or ())],
            }
            for one in work.scalars(
                select(Dimension)
                .where(Dimension.rubric_id == chosen.rubric_id)
                .order_by(Dimension.dimension_id)
            )
        ]
        constraints = [
            {
                "constraint_id": one.constraint_id,
                "name": one.name,
                "check_type": one.check_type,
                "params": dict(one.params or {}),
                "section_types": [str(item) for item in (one.section_types or ())],
            }
            for one in work.scalars(
                select(Constraint)
                .where(Constraint.contest_id == name)
                .order_by(Constraint.constraint_id)
            )
        ]

    return {
        "rubric_id": chosen.rubric_id,
        "rubric_version": int(chosen.version),
        "dimensions": dimensions,
        "constraints": constraints,
    }
