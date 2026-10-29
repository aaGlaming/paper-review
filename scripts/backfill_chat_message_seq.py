"""显式回填聊天消息会话内序号；默认保留非零 seq，--force 才重排全部历史。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.chat.models import ChatMessage, create_chat_schema
from backend.app.importing import db


def backfill(session: Session, *, force: bool = False) -> tuple[int, int, int]:
    """按既有稳定排序编号；非零历史不动，重复执行更新数为零。"""
    messages = list(session.scalars(select(ChatMessage).order_by(
        ChatMessage.session_id, ChatMessage.created_at, ChatMessage.message_id,
    )))
    sessions = updated = skipped = 0
    previous = None
    number = 0
    for message in messages:
        if message.session_id != previous:
            sessions += 1
            previous = message.session_id
            number = 0
        number += 1
        if message.seq != 0 and not force:
            skipped += 1
            continue
        if message.seq == number:
            skipped += 1
            continue
        message.seq = number
        updated += 1
    session.flush()
    return sessions, updated, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="回填聊天消息会话内序号")
    parser.add_argument("--force", action="store_true", help="重新编号所有历史消息")
    args = parser.parse_args()
    create_chat_schema()
    with db.session_scope() as session:
        sessions, updated, skipped = backfill(session, force=args.force)
    print(f"会话数={sessions} / 更新行数={updated} / 跳过行数={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
