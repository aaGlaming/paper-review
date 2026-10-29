from datetime import datetime
from itertools import count

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.chat import store
from backend.app.chat.models import ChatMessage, create_chat_schema


@pytest.fixture()
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_chat_schema(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_five_messages_in_same_second_preserve_write_order_twenty_times(session, monkeypatch):
    ids = count(1000, -1)
    monkeypatch.setattr(store, "new_message_id", lambda: f"{next(ids):032x}")
    same_second = datetime(2026, 1, 1)
    for iteration in range(20):
        owner = store.create_session(session, "teacher")
        expected = [f"round-{iteration}-message-{index}" for index in range(5)]
        for content in expected:
            row = store.append_message(session, owner.session_id, "user", content)
            row.created_at = same_second
        session.flush()
        session.expire_all()
        loaded = store.load_messages(session, owner.session_id)
        assert [row.created_at for row in loaded] == [same_second] * 5
        assert [row.content for row in loaded] == expected


def test_new_message_sequence_starts_at_one_and_increments(session):
    owner = store.create_session(session, "teacher")
    rows = [store.append_message(session, owner.session_id, "user", str(i)) for i in range(5)]
    assert [row.seq for row in rows] == [1, 2, 3, 4, 5]


def test_legacy_zero_sequence_messages_remain_readable(session):
    owner = store.create_session(session, "teacher")
    same_second = datetime(2026, 1, 1)
    for message_id in ("b", "a"):
        session.add(ChatMessage(message_id=message_id, session_id=owner.session_id,
                                role="user", content=message_id, seq=0, created_at=same_second))
    session.flush()
    loaded = store.load_messages(session, owner.session_id)
    assert [(row.message_id, row.seq) for row in loaded] == [("a", 0), ("b", 0)]


def test_sequence_is_independent_for_each_session(session):
    first = store.create_session(session, "teacher")
    second = store.create_session(session, "teacher")
    assert store.append_message(session, first.session_id, "user", "one").seq == 1
    assert store.append_message(session, first.session_id, "user", "two").seq == 2
    assert store.append_message(session, second.session_id, "user", "one").seq == 1
