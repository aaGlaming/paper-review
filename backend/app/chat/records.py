"""把已落档评审转换为现有父子块格式，并索引到共享检索库。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete

from ..report import store as report_store
from ..retrieve import models as retrieve_models
from ..retrieve import parent_child
from ..retrieve.parent_child import ChildChunk, ParentBlock


def _related_suggestions(change_list: list[dict[str, Any]], dimension_code: str) -> list[str]:
    result = []
    for item in change_list:
        upstream = str(item.get("upstream_id") or "")
        if str(item.get("dimension_code") or "") != dimension_code and upstream != f"dimension:{dimension_code}":
            continue
        text = str(item.get("text") or item.get("action") or "")[:80]
        if text:
            result.append(f"{item.get('kind') or '建议'}: {text}")
        if len(result) == 3:
            break
    return result


def build_review_record(
    review: dict[str, Any], *, contest_id: str, rubric_id: str
) -> tuple[list[ParentBlock], list[ChildChunk]]:
    review_id = str(review.get("review_id") or "")
    parents: list[ParentBlock] = []
    children: list[ChildChunk] = []
    change_list = [item for item in review.get("change_list") or () if isinstance(item, dict)]

    for dimension in review.get("dimensions") or ():
        if not isinstance(dimension, dict):
            continue
        code = str(dimension.get("dimension_code") or dimension.get("code") or "")
        if not code:
            continue
        band = str(dimension.get("band") or "").strip()
        quote = str(dimension.get("quote") or "").strip()
        if not band and not quote:
            continue
        suggestions = _related_suggestions(change_list, code)
        content = "\n".join((
            f"【维度】{code} 【档位】{band or '未选档'}",
            f"【原句】{quote or '无'}",
            f"【关联建议】{'；'.join(suggestions) if suggestions else '无'}",
        ))
        parent_id = f"rr-{review_id}-{code}"
        child_text = f"赛题 {contest_id} 记录 {review_id} 维度 {code}\n{content}"
        parents.append(ParentBlock(
            parent_id=parent_id,
            section_type="评审记录",
            content=content,
            review_id=review_id,
            char_span=(0, len(content)),
        ))
        children.append(ChildChunk(
            chunk_id=parent_id,
            parent_id=parent_id,
            contest_id=str(contest_id),
            rubric_id=str(rubric_id),
            dimension_code=code,
            section_type="评审记录",
            text=child_text,
            char_start=0,
            char_end=len(child_text),
            doc_type="review_record",
            review_id=review_id,
        ))
    return parents, children


def load_record_blocks(review_id: str, *, session: Any = None) -> list[dict[str, Any]]:
    """Load exact review parents from MySQL without consulting the vector index."""
    review = report_store.load_review(str(review_id), session=session)
    if review is None:
        return []
    parents, _ = build_review_record(
        review,
        contest_id=str(review.get("contest_id") or ""),
        rubric_id=str(review.get("rubric_id") or ""),
    )
    blocks: list[dict[str, Any]] = []
    for parent in parents:
        blocks.append({
            "review_id": str(review_id),
            "dimension_code": parent.parent_id.rsplit("-", 1)[1],
            "parent_id": parent.parent_id,
            "content": parent.content,
            "citable": True,
        })

    raw_changes = review.get("change_list") or []
    if isinstance(raw_changes, str):
        try:
            raw_changes = json.loads(raw_changes)
        except (TypeError, ValueError):
            raw_changes = None
    overview = [
        f"赛题：{review.get('contest_id') or '未知'}",
        f"提交时间：{review.get('created_at') or review.get('submitted_at') or '未知'}",
        "五维档位：" + " / ".join(
            f"{item.get('dimension_code') or item.get('code') or '未知'} {item.get('band') or '未选档'}"
            for item in (review.get("dimensions") or ()) if isinstance(item, dict)
        ),
    ]
    if raw_changes is None:
        overview.append("修改条目解析失败")
    else:
        changes = [item for item in raw_changes if isinstance(item, dict)] if isinstance(raw_changes, list) else []
        for item in changes[:12]:
            text = str(item.get("text") or item.get("action") or "")[:80]
            overview.append(
                f"[{item.get('kind') or '建议'}] {item.get('target') or ''} → {text}"
            )
        if len(changes) > 12:
            overview.append(f"另 {len(changes) - 12} 条略")
    blocks.append({
        "review_id": str(review_id),
        "dimension_code": "record_summary",
        "parent_id": f"rr-{review_id}-overview",
        "content": "\n".join(overview),
        "citable": False,
    })
    return blocks


def _delete_parent_blocks(review_id: str) -> None:
    from ..importing import db

    with db.session_scope() as session:
        session.execute(delete(retrieve_models.PaperParent).where(
            retrieve_models.PaperParent.review_id == review_id,
            retrieve_models.PaperParent.parent_id.like(f"rr-{review_id}-%"),
        ))


def index_review_record(review_id: str, session: Any = None, client: Any = None) -> int:
    collection = parent_child.get_collection(client)
    try:
        existing = collection.get(where={"$and": [
            {"review_id": str(review_id)},
            {"doc_type": "review_record"},
        ]})
        ids = [str(item) for item in existing.get("ids", ())]
    except Exception:
        ids = []
    if not ids:
        from ..report.models import ReviewDimension
        from sqlalchemy import select

        if session is not None:
            dimensions = list(session.scalars(
                select(ReviewDimension.dimension_code).where(
                    ReviewDimension.review_id == str(review_id)
                )
            ))
        else:
            from ..importing import db

            with db.session_scope() as work:
                dimensions = list(work.scalars(
                    select(ReviewDimension.dimension_code).where(
                        ReviewDimension.review_id == str(review_id)
                    )
                ))
        ids = [f"rr-{review_id}-{code}" for code in dimensions]
    if ids:
        collection.delete(ids=ids)

    review = report_store.load_review(str(review_id), session=session)
    if not review:
        _delete_parent_blocks(str(review_id))
        return 0
    parents, children = build_review_record(
        review,
        contest_id=str(review.get("contest_id") or ""),
        rubric_id=str(review.get("rubric_id") or ""),
    )
    if not parents:
        _delete_parent_blocks(str(review_id))
        return 0

    parent_child.save_parents(parents)
    if children:
        # 与现有父子检索共用向量客户端；本阶段只嵌入索引文本，不生成回答。
        from ..llm import client as llm_client

        vectors = llm_client.embed([child.text for child in children])
        parent_child.index_children(children, client=client, embeddings=vectors)
    return len(children)


def delete_review_record(review_id: str, client: Any = None) -> None:
    collection = parent_child.get_collection(client)
    try:
        existing = collection.get(where={"$and": [
            {"review_id": str(review_id)},
            {"doc_type": "review_record"},
        ]})
        ids = [str(item) for item in existing.get("ids", ())]
    except Exception:
        ids = []
    if not ids:
        from ..report.models import ReviewDimension
        from sqlalchemy import select
        from ..importing import db

        with db.session_scope() as session:
            dimensions = list(session.scalars(
                select(ReviewDimension.dimension_code).where(
                    ReviewDimension.review_id == str(review_id)
                )
            ))
        ids = [f"rr-{review_id}-{code}" for code in dimensions]
    if ids:
        collection.delete(ids=ids)
    _delete_parent_blocks(str(review_id))
