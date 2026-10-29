"""P19 会话与消息底座：权限、隔离、持久化与审计。"""

from __future__ import annotations

import json
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.app import create_app
from backend.app.api.routes import get_session
from backend.app.auth import store as auth_store
from backend.app.auth.models import User, create_auth_schema
from backend.app.auth.security import hash_password
from backend.app.auth.token import issue_token
from backend.app.chat import models as chat_models
from backend.app.chat import store as chat_store
from backend.app.observability import logging as logging_mod


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_auth_schema(engine)
    chat_models.create_chat_schema(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def client(engine, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", secrets.token_urlsafe(48))
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _scope():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(auth_store, "session_scope_cm", _scope)

    def _override_session():
        with _scope() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(engine, username, role):
    with Session(engine) as session:
        row = auth_store.create_user(
            session,
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password("test-password-123"),
            role=role,
        )
        session.commit()
        return row.user_id


def _token(engine, user_id):
    with Session(engine) as session:
        row = session.get(User, user_id)
        return issue_token(row.user_id, row.role, row.password_hash)


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def actors(engine):
    return {
        "student": _user(engine, "chat-student", "student"),
        "teacher": _user(engine, "chat-teacher", "teacher"),
        "teacher2": _user(engine, "chat-teacher2", "teacher"),
    }


def test_student_chat_permission_denies_list_and_create(client, engine, actors):
    headers = _headers(_token(engine, actors["student"]))
    assert client.get("/api/chat/sessions", headers=headers).status_code == 403
    assert client.post("/api/chat/sessions", headers=headers, json={}).status_code == 403


def test_teacher_create_session_uses_default_and_requested_title(client, engine, actors):
    headers = _headers(_token(engine, actors["teacher"]))
    default = client.post("/api/chat/sessions", headers=headers, json={})
    titled = client.post("/api/chat/sessions", headers=headers, json={"title": "课后讨论"})
    assert default.status_code == 201
    assert default.json()["title"] == "新会话"
    assert titled.status_code == 201
    assert titled.json()["title"] == "课后讨论"


def test_session_title_is_truncated_to_256(client, engine, actors):
    response = client.post(
        "/api/chat/sessions", headers=_headers(_token(engine, actors["teacher"])),
        json={"title": "x" * 300},
    )
    assert response.status_code == 201
    assert len(response.json()["title"]) == 256


def test_list_sessions_sorts_updated_descending(client, engine, actors):
    headers = _headers(_token(engine, actors["teacher"]))
    first = client.post("/api/chat/sessions", headers=headers, json={}).json()
    second = client.post("/api/chat/sessions", headers=headers, json={}).json()
    # Use distinct timestamps so the ordering assertion does not depend on two
    # requests landing in the same clock tick; equal timestamps use session_id.
    with Session(engine) as session:
        base = datetime(2026, 1, 1)
        session.get(chat_models.ChatSession, first["session_id"]).updated_at = base
        session.get(chat_models.ChatSession, second["session_id"]).updated_at = base + timedelta(seconds=1)
        session.commit()
    response = client.get("/api/chat/sessions", headers=headers)
    assert [item["session_id"] for item in response.json()["sessions"]] == [
        second["session_id"], first["session_id"]
    ]


def test_list_sessions_message_counts(client, engine, actors):
    headers = _headers(_token(engine, actors["teacher"]))
    one = client.post("/api/chat/sessions", headers=headers, json={}).json()["session_id"]
    two = client.post("/api/chat/sessions", headers=headers, json={}).json()["session_id"]
    with Session(engine) as session:
        for index in range(3):
            chat_store.append_message(session, one, "user", f"message {index}")
        session.commit()
    counts = {item["session_id"]: item["message_count"] for item in
              client.get("/api/chat/sessions", headers=headers).json()["sessions"]}
    assert counts == {one: 3, two: 0}


def test_messages_are_ordered_and_refs_are_null(client, engine, actors):
    headers = _headers(_token(engine, actors["teacher"]))
    session_id = client.post("/api/chat/sessions", headers=headers, json={}).json()["session_id"]
    with Session(engine) as session:
        chat_store.append_message(session, session_id, "assistant", "second")
        chat_store.append_message(session, session_id, "user", "first")
        session.commit()
    response = client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers)
    assert response.status_code == 200
    assert [message["content"] for message in response.json()["messages"]] == ["second", "first"]
    assert [message["seq"] for message in response.json()["messages"]] == [1, 2]
    assert all(message["refs"] is None for message in response.json()["messages"])


def test_other_teacher_session_is_same_404_as_missing(client, engine, actors):
    owner_headers = _headers(_token(engine, actors["teacher"]))
    visitor_headers = _headers(_token(engine, actors["teacher2"]))
    session_id = client.post("/api/chat/sessions", headers=owner_headers, json={}).json()["session_id"]
    hidden = client.get(f"/api/chat/sessions/{session_id}/messages", headers=visitor_headers)
    missing = client.get("/api/chat/sessions/does-not-exist/messages", headers=visitor_headers)
    assert hidden.status_code == missing.status_code == 404
    assert hidden.content == missing.content
    assert hidden.json()["detail"] == "找不到问询会话"


def test_delete_session_removes_messages_first(client, engine, actors):
    headers = _headers(_token(engine, actors["teacher"]))
    session_id = client.post("/api/chat/sessions", headers=headers, json={}).json()["session_id"]
    with Session(engine) as session:
        chat_store.append_message(session, session_id, "user", "stored")
        session.commit()
    assert client.delete(f"/api/chat/sessions/{session_id}", headers=headers).status_code == 204
    assert client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers).status_code == 404
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(chat_models.ChatMessage)) == 0


def test_cannot_delete_another_teachers_session(client, engine, actors):
    owner_headers = _headers(_token(engine, actors["teacher"]))
    visitor_headers = _headers(_token(engine, actors["teacher2"]))
    session_id = client.post("/api/chat/sessions", headers=owner_headers, json={}).json()["session_id"]
    hidden = client.delete(f"/api/chat/sessions/{session_id}", headers=visitor_headers)
    missing = client.delete("/api/chat/sessions/does-not-exist", headers=visitor_headers)
    assert hidden.status_code == missing.status_code == 404
    assert hidden.content == missing.content
    with Session(engine) as session:
        assert session.get(chat_models.ChatSession, session_id) is not None


def test_append_message_rejects_unknown_role(engine, actors):
    with Session(engine) as session:
        row = chat_store.create_session(session, actors["teacher"])
        with pytest.raises(ValueError, match="role"):
            chat_store.append_message(session, row.session_id, "system", "no")


def test_create_chat_schema_is_idempotent(engine):
    chat_models.create_chat_schema(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"chat_session", "chat_message"} <= tables


def test_session_created_log_contains_ids_but_no_content(
    client, engine, actors, tmp_path, monkeypatch
):
    monkeypatch.delenv("LOG_DISABLED", raising=False)
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    logging_mod.reset_logging_for_tests()
    try:
        response = client.post(
            "/api/chat/sessions", headers=_headers(_token(engine, actors["teacher"])),
            json={"title": "private title"},
        )
        assert response.status_code == 201
        logging_mod.reset_logging_for_tests()
        files = list((tmp_path / "ai_chat").glob("*.log"))
        events = [json.loads(line) for path in files for line in path.read_text(encoding="utf-8").splitlines()]
        created = next(event for event in events if event["event"] == "session_created")
        assert created["session_id"] == response.json()["session_id"]
        assert created["user_id"] == actors["teacher"]
        assert "content" not in created
        assert "private title" not in json.dumps(created, ensure_ascii=False)
    finally:
        logging_mod.reset_logging_for_tests()

