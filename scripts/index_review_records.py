"""显式回填评审记录到共享父子块索引，不修改 review 表。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from backend.app.chat.records import build_review_record, index_review_record
from backend.app.importing import db
from backend.app.report.models import Review
from backend.app.report.store import load_review
from backend.app.retrieve import parent_child
from backend.app.retrieve.parent_child import get_collection

LOCK_PATH = PROJECT_ROOT / ".index_review_records.lock"
ALREADY_RUNNING = 2


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # Windows 的 os.kill(pid, 0) 不能用于安全探测进程存活。
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # 权限不足按存活处理；87 为 pid 不存在。
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextmanager
def single_instance(path: Path = LOCK_PATH) -> Iterator[bool]:
    """独占创建锁文件；保守处理未写完的锁，并只清理自己持有的锁。"""
    owner = {"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat(),
             "token": uuid.uuid4().hex}
    handle = None
    while handle is None:
        try:
            handle = path.open("x", encoding="utf-8")
        except FileExistsError:
            try:
                snapshot = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                continue
            try:
                existing = json.loads(snapshot)
                pid = int(existing["pid"])
                started = str(existing["started_at"])
            except (ValueError, TypeError, KeyError):
                print("另一个回填进程正在运行（pid=未知，开始于 未知；锁内容尚不可读）", flush=True)
                yield False
                return
            if _pid_exists(pid):
                print(f"另一个回填进程正在运行（pid={pid}，开始于 {started}）", flush=True)
                yield False
                return
            try:
                if path.read_text(encoding="utf-8") != snapshot:
                    continue
                path.unlink()
            except FileNotFoundError:
                continue
            print(f"接管陈旧回填锁（原 pid={pid}，开始于 {started}）", flush=True)
    try:
        json.dump(owner, handle, ensure_ascii=False)
        handle.flush()
        yield True
    finally:
        handle.close()
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("token") == owner["token"]:
                path.unlink()
        except FileNotFoundError:
            pass


def run_exclusively(action: Callable[[], int], *, lock_path: Path = LOCK_PATH) -> int:
    with single_instance(lock_path) as acquired:
        return action() if acquired else ALREADY_RUNNING


def _record_is_current(review_id: str, collection) -> bool:
    """父块正文、子块正文及元数据都一致才跳过，不用数量相同冒充已同步。"""
    review = load_review(review_id)
    if review is None:
        return False
    parents, children = build_review_record(
        review, contest_id=str(review.get("contest_id") or ""),
        rubric_id=str(review.get("rubric_id") or ""),
    )
    if not children:
        return False
    actual_parents = parent_child.get_parents(parent.parent_id for parent in parents)
    expected_parents = {parent.parent_id: parent for parent in parents}
    if {parent.parent_id: parent for parent in actual_parents} != expected_parents:
        return False
    found = collection.get(where={"$and": [
        {"review_id": str(review_id)}, {"doc_type": "review_record"},
    ]}, include=["documents", "metadatas"])
    actual = {
        chunk_id: (document, metadata)
        for chunk_id, document, metadata in zip(
            found.get("ids") or [], found.get("documents") or [], found.get("metadatas") or [],
        )
    }
    expected = {child.chunk_id: (child.text, parent_child.child_metadata(child)) for child in children}
    return actual == expected


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


def _run(review_ids: list[str], *, client, dry_run: bool) -> int:
    collection = get_collection(client)
    before = collection.count()
    if dry_run:
        indexed, children, skipped, failed = _dry_run(review_ids)
    else:
        indexed = children = skipped = 0
        failed = []
        for review_id in review_ids:
            try:
                if _record_is_current(review_id, collection):
                    skipped += 1
                    continue
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
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="索引评审记录到共享检索库")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="扫描全部评审记录")
    group.add_argument("--review-id", help="仅索引指定评审记录")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写父表或向量库")
    args = parser.parse_args()
    if args.dry_run and not args.all:
        parser.error("--dry-run 仅支持与 --all 一起使用")

    def action() -> int:
        review_ids = _review_ids() if args.all else [str(args.review_id)]
        return _run(review_ids, client=None, dry_run=args.dry_run)

    return run_exclusively(action)


if __name__ == "__main__":
    raise SystemExit(main())
