"""Rebuild the persistent paper collection from canonical MySQL parent blocks."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from backend.app.importing import db
from backend.app.importing.models import Rubric
from backend.app.llm import client as llm_client
from backend.app.report.models import Review, ReviewSession
from backend.app.retrieve import parent_child
from backend.app.retrieve.models import PaperParent


def main() -> int:
    parent_child.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    vector_client = parent_child.default_client()
    collection = parent_child.get_collection(vector_client)
    print(f"collection_count_before={collection.count()}", flush=True)

    with db.session_scope() as session:
        reviews = {row.review_id: row for row in session.scalars(select(Review))}
        sessions = {row.review_id: row for row in session.scalars(select(ReviewSession))}
        rubrics: dict[str, str] = {}
        for row in session.scalars(select(Rubric).order_by(Rubric.version.desc())):
            rubrics.setdefault(row.contest_id, row.rubric_id)
        parents = list(session.scalars(
            select(PaperParent).order_by(PaperParent.review_id, PaperParent.parent_id)
        ))

    papers = [row for row in parents if row.section_type != "评审记录" and not row.parent_id.startswith("rr-")]
    children = []
    skipped = 0
    for row in papers:
        review = reviews.get(row.review_id)
        snapshot = sessions.get(row.review_id)
        contest_id = str(
            (review.contest_id if review else None)
            or (snapshot.contest_id if snapshot else "")
        )
        rubric_id = str(
            (review.rubric_id if review else None)
            or rubrics.get(contest_id, "")
        )
        if not contest_id or not rubric_id:
            skipped += 1
            continue
        parent = parent_child.ParentBlock(
            parent_id=row.parent_id,
            section_type=row.section_type,
            content=row.content,
            review_id=row.review_id,
            char_span=tuple(row.char_span) if row.char_span else None,
        )
        children.extend(parent_child.build_children(
            parent,
            contest_id=contest_id,
            rubric_id=rubric_id,
            dimension_code="paper",
            review_id=row.review_id,
        ))

    print(f"paper_parents={len(papers)} paper_children={len(children)} skipped_parents={skipped}", flush=True)
    batch_size = 64
    for offset in range(0, len(children), batch_size):
        batch = children[offset:offset + batch_size]
        vectors = llm_client.embed([child.text for child in batch])
        parent_child.index_children(batch, client=vector_client, embeddings=vectors)
        print(f"indexed_paper_children={min(offset + len(batch), len(children))}/{len(children)}", flush=True)

    from backend.app.chat.records import index_review_record
    from backend.app.report.models import Review as ReviewModel

    session = db.get_session_factory()()
    try:
        review_ids = [str(item) for item in session.scalars(
            select(ReviewModel.review_id).order_by(ReviewModel.review_id)
        )]
        indexed_reviews = total_review_children = 0
        for review_id in review_ids:
            count = index_review_record(review_id, session=session, client=vector_client)
            indexed_reviews += int(count > 0)
            total_review_children += count
    finally:
        session.close()
    print(f"indexed_review_records={indexed_reviews} review_children={total_review_children}", flush=True)
    print(f"collection_count_after={collection.count()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
