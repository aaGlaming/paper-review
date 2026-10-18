"""评审记录读写。

保存内容含赛题编号、量规版本、模型名与每维的档位 / 切片编号 / 原句；打开旧 `review_id` 时这些
信息原样还在。**旧记录一律不回写**：同一 `review_id` 再次保存时，身份字段（赛题、量规、版本、
模型名、创建时间）与当时各维的档位 / 切片编号 / 原句都保持不变——发布新版量规只影响之后新建的
评审单，要改旧记录就换一个新的 `review_id`。

`save_session` / `load_session` 读写的是章节确认之前的会话快照，与上面不同：同一 `review_id`
再次保存会**覆盖**上一次的快照（确认时以调用方给的章节树为准），因为没有第二处存档可依据。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Review, ReviewDimension, ReviewSession, utc_now

_DIMENSION_FIELDS = ("dimension_code", "band", "chunk_ids", "quote", "status")


@contextmanager
def _session(session: Session | None) -> Iterator[Session]:
    """有外部会话就用它（不提交，由调用方决定），否则自己开一个并提交。"""
    if session is not None:
        yield session
        return
    from ..importing import db

    with db.session_scope() as owned:
        yield owned


def _normalize_dimensions(dimensions: Any) -> list[dict[str, Any]]:
    """接受 {code: {...}} 或 [{"dimension_code": ...}, ...] 两种写法。"""
    if isinstance(dimensions, Mapping):
        items = [{"dimension_code": code, **(value if isinstance(value, Mapping) else {})} for code, value in dimensions.items()]
    else:
        items = list(dimensions or ())
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        code = str(item.get("dimension_code") or item.get("code") or "")
        if not code:
            continue
        normalized.append(
            {
                "dimension_code": code,
                "band": item.get("band"),
                "chunk_ids": [str(chunk) for chunk in (item.get("chunk_ids") or ())],
                "quote": item.get("quote"),
                "status": item.get("status") or item.get("band"),
            }
        )
    return normalized


def _to_dict(row: Review, dimensions: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    result = {
        "review_id": row.review_id,
        "contest_id": row.contest_id,
        "rubric_id": row.rubric_id,
        "rubric_version": row.rubric_version,
        "model_name": row.model_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "dimensions": [
            {field: item.get(field) for field in _DIMENSION_FIELDS} for item in dimensions
        ],
        "change_list": [dict(item) for item in (row.change_list or ())],
    }
    if row.change_list is None:
        result["change_list_note"] = "该记录为旧数据，未保存审查清单"
    else:
        result["change_list_note"] = None
    return result


def save_review(
    review_id: str,
    *,
    contest_id: str = "",
    rubric_id: str = "",
    rubric_version: int = 1,
    model_name: str = "",
    dimensions: Any = None,
    change_list: Any = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """保存一条评审记录与它的各维结果。已存在的记录不回写，原样返回当时的存档。"""
    with _session(session) as work:
        row = work.get(Review, review_id)
        if row is not None:
            return _load_with(work, row)
        row = Review(
            review_id=review_id,
            contest_id=str(contest_id),
            rubric_id=str(rubric_id),
            rubric_version=int(rubric_version),
            model_name=str(model_name),
            created_at=utc_now(),
            change_list=[dict(item) for item in (change_list or ()) if isinstance(item, Mapping)],
        )
        work.add(row)
        work.flush()
        items = _normalize_dimensions(dimensions)
        for item in items:
            work.add(
                ReviewDimension(
                    review_id=review_id,
                    dimension_code=item["dimension_code"],
                    band=item["band"],
                    chunk_ids=item["chunk_ids"],
                    quote=item["quote"],
                    status=item["status"],
                )
            )
        work.flush()
        return _to_dict(row, items)


def _load_with(work: Session, row: Review) -> dict[str, Any]:
    stored = list(
        work.scalars(
            select(ReviewDimension)
            .where(ReviewDimension.review_id == row.review_id)
            .order_by(ReviewDimension.dimension_code)
        )
    )
    return _to_dict(
        row,
        [
            {
                field: getattr(item, field)
                for field in _DIMENSION_FIELDS
            }
            for item in stored
        ],
    )


def load_review(review_id: str, *, session: Session | None = None) -> dict[str, Any] | None:
    """按 review_id 取回评审记录；找不到返回 None。"""
    with _session(session) as work:
        row = work.get(Review, review_id)
        if row is None:
            return None
        return _load_with(work, row)


def _session_to_dict(row: ReviewSession) -> dict[str, Any]:
    return {
        "review_id": row.review_id,
        "paper_text": row.paper_text,
        "sections": [dict(section) for section in (row.sections or [])],
        "confirmed": bool(row.confirmed),
        "status": row.status,
        "contest_id": row.contest_id,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def save_session(
    review_id: str,
    *,
    paper_text: str = "",
    sections: Iterable[Mapping[str, Any]] | None = None,
    confirmed: bool = False,
    status: str = "",
    contest_id: str = "",
    session: Session | None = None,
) -> dict[str, Any]:
    """写一份评审会话快照。同一 `review_id` 再次调用是覆盖，不是新增。"""
    with _session(session) as work:
        row = work.get(ReviewSession, review_id)
        if row is None:
            row = ReviewSession(review_id=review_id)
            work.add(row)
        row.paper_text = str(paper_text)
        row.sections = [dict(section) for section in (sections or ())]
        row.confirmed = bool(confirmed)
        row.status = str(status)
        row.contest_id = str(contest_id)
        row.updated_at = utc_now()
        work.flush()
        return _session_to_dict(row)


def load_session(review_id: str, *, session: Session | None = None) -> dict[str, Any] | None:
    """按 review_id 取回会话快照；找不到返回 None。"""
    with _session(session) as work:
        row = work.get(ReviewSession, review_id)
        if row is None:
            return None
        return _session_to_dict(row)
