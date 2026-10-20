"""显式回填评审记录到共享父子块索引，不修改 review 表。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from backend.app.chat.records import build_review_record, index_review_record
from backend.app.importing import db
from backend.app.report.models import Review
from backend.app.report.store import load_review
from backend.app.retrieve.parent_child import get_collection


def _review_ids() -> list[str]:
    with db.session_scope() as session:
        return list(session.scalars(select(Review.review_id).order_by(Review.review_id.asc())).all())


def _dry_run(review_ids: list[str]) -> tuple[int, int, int, list[str]]:
    indexed = children = skipped = 0
    failed: list[str] = []
    for review_id in review_ids:
        try:
            review = load_review(review_id)
            if review is None:
                skipped += 1
                continue
            _parents, chunks = build_review_record(
                review,
                contest_id=str(review.get("contest_id") or ""),
                rubric_id=str(review.get("rubric_id") or ""),
            )
            if chunks:
                indexed += 1
                children += len(chunks)
            else:
                skipped += 1
        except Exception as exc:  # 单条记录问题不能阻断全量统计
            failed.append(review_id)
            print(f"failed review_id={review_id} error={type(exc).__name__}")
    return indexed, children, skipped, failed


def _run(review_ids: list[str], *, client, dry_run: bool) -> None:
    before = get_collection(client).count()
    if dry_run:
        indexed, children, skipped, failed = _dry_run(review_ids)
    else:
        indexed = children = skipped = 0
        failed = []
        for review_id in review_ids:
            try:
                count = index_review_record(review_id, client=client)
                if count:
                    indexed += 1
                    children += count
                else:
                    skipped += 1
            except Exception as exc:  # 回填不中断，最终汇总失败 ID
                failed.append(review_id)
                print(f"failed review_id={review_id} error={type(exc).__name__}")
    after = get_collection(client).count()
    print(f"indexed={indexed} reviews, {children} children, skipped={skipped}")
    print(f"collection_count_before={before} collection_count_after={after}")
    if failed:
        print("failed_review_ids=" + ",".join(failed))


def main() -> int:
    parser = argparse.ArgumentParser(description="索引评审记录到共享检索库")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="扫描全部评审记录")
    group.add_argument("--review-id", help="仅索引指定评审记录")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写父表或向量库")
    args = parser.parse_args()
    if args.dry_run and not args.all:
        parser.error("--dry-run 仅支持与 --all 一起使用")

    review_ids = _review_ids() if args.all else [str(args.review_id)]
    _run(review_ids, client=None, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
