"""P19 问答回答链路：检索引用、模型重试与消息持久化。"""

from __future__ import annotations

import secrets
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
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
    monkeypatch.setenv("LLM_MODEL", "test-model")
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


def _create_user(engine, username: str, role: str) -> str:
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


@pytest.fixture()
def actors(engine):
    return {
        "student": _create_user(engine, "answer-student", "student"),
        "teacher": _create_user(engine, "answer-teacher", "teacher"),
        "teacher2": _create_user(engine, "answer-teacher2", "teacher"),
    }


def _headers(engine, user_id: str) -> dict[str, str]:
    with Session(engine) as session:
        row = session.get(User, user_id)
        token = issue_token(row.user_id, row.role, row.password_hash)
    return {"Authorization": f"Bearer {token}"}


def _new_session(client, engine, teacher_id: str) -> str:
    response = client.post("/api/chat/sessions", headers=_headers(engine, teacher_id), json={})
    assert response.status_code == 201
    return response.json()["session_id"]


def _hit(review_id: str, dimension_code: str = "assumption") -> dict[str, str]:
    return {
        "review_id": review_id,
        "dimension_code": dimension_code,
        "parent_id": f"rr-{review_id}-{dimension_code}",
        "content": "【维度】assumption 【档位】基本\n【原句】样例原句",
    }


def _install_fakes(client, monkeypatch, search_fn, chat_fn):
    from backend.app.api import chat_routes

    app = client.app
    if hasattr(chat_routes, "get_search_fn"):
        app.dependency_overrides[chat_routes.get_search_fn] = lambda: search_fn
    if hasattr(chat_routes, "get_chat_fn"):
        app.dependency_overrides[chat_routes.get_chat_fn] = lambda: chat_fn
    if not hasattr(chat_routes, "get_search_fn"):
        monkeypatch.setattr(chat_routes, "search_records", search_fn, raising=False)
    if not hasattr(chat_routes, "get_chat_fn"):
        monkeypatch.setattr(chat_routes, "chat", chat_fn, raising=False)


def _post_answer(client, engine, teacher_id: str, session_id: str, **body):
    return client.post(
        f"/api/chat/sessions/{session_id}/messages",
        headers=_headers(engine, teacher_id),
        json=body,
    )


def test_student_cannot_post_chat_answer(client, engine, actors):
    session_id = _new_session(client, engine, actors["teacher"])
    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        headers=_headers(engine, actors["student"]),
        json={"question": "问题", "contest_id": "contest-a"},
    )
    assert response.status_code == 403


def test_other_teacher_session_answer_is_same_404_as_missing(client, engine, actors):
    session_id = _new_session(client, engine, actors["teacher"])
    headers = _headers(engine, actors["teacher2"])
    hidden = client.post(
        f"/api/chat/sessions/{session_id}/messages", headers=headers,
        json={"question": "问题", "contest_id": "contest-a"},
    )
    missing = client.post(
        "/api/chat/sessions/not-a-real-session/messages", headers=headers,
        json={"question": "问题", "contest_id": "contest-a"},
    )
    assert hidden.status_code == missing.status_code == 404
    assert hidden.content == missing.content


def test_answer_request_validation_rejects_empty_long_and_missing_scope(client, engine, actors):
    session_id = _new_session(client, engine, actors["teacher"])
    headers = _headers(engine, actors["teacher"])
    base = f"/api/chat/sessions/{session_id}/messages"
    empty = client.post(base, headers=headers, json={"question": "  ", "contest_id": "c"})
    too_long = client.post(base, headers=headers, json={"question": "x" * 2001, "contest_id": "c"})
    missing_scope = client.post(base, headers=headers, json={"question": "有效问题"})
    assert [empty.status_code, too_long.status_code, missing_scope.status_code] == [400, 400, 400]


def test_empty_retrieval_does_not_call_model(client, engine, actors, monkeypatch):
    session_id = _new_session(client, engine, actors["teacher"])
    calls = {"search": 0, "chat": 0}

    def search_fn(*args, **kwargs):
        calls["search"] += 1
        return []

    def chat_fn(messages):
        calls["chat"] += 1
        return "不可达"

    _install_fakes(client, monkeypatch, search_fn, chat_fn)
    response = _post_answer(
        client, engine, actors["teacher"], session_id,
        question="请说明记录", contest_id="contest-a",
    )
    assert response.status_code == 200
    assert "没有相关信息" in response.json()["content"]
    assert response.json()["refs"] == []
    assert calls == {"search": 1, "chat": 0}


def test_answer_persists_user_and_assistant_with_refs(client, engine, actors, monkeypatch):
    session_id = _new_session(client, engine, actors["teacher"])
    hit = _hit("a" * 32)
    _install_fakes(client, monkeypatch, lambda *a, **k: [hit],
                   lambda messages: "结论 [review_id=" + hit["review_id"] + " dim=assumption]")
    response = _post_answer(
        client, engine, actors["teacher"], session_id,
        question="请说明记录", contest_id="contest-a",
    )
    assert response.status_code == 200
    assert len(response.json()["refs"]) == 1
    with Session(engine) as session:
        messages = chat_store.load_messages(session, session_id)
    assert [row.role for row in messages] == ["user", "assistant"]
    assert messages[1].refs == [{"review_id": hit["review_id"], "dimension_code": "assumption"}]
    assert messages[1].model_name


def test_answer_removes_citations_outside_retrieval_set(client, engine, actors, monkeypatch):
    session_id = _new_session(client, engine, actors["teacher"])
    allowed = _hit("a" * 32)
    _install_fakes(
        client, monkeypatch, lambda *a, **k: [allowed],
        lambda messages: "结论 [review_id=" + allowed["review_id"] + " dim=assumption] "
        "[review_id=outside dim=method]",
    )
    response = _post_answer(
        client, engine, actors["teacher"], session_id,
        question="请说明记录", contest_id="contest-a",
    )
    assert response.status_code == 200
    assert "outside" not in response.json()["content"]
    assert response.json()["notifications"]["rejected"] == 1


def test_answer_counts_retrieved_but_uncited_records(client, engine, actors, monkeypatch):
    session_id = _new_session(client, engine, actors["teacher"])
    hits = [_hit(f"{number:032x}") for number in range(3)]
    citation = f"[review_id={hits[0]['review_id']} dim=assumption]"
    _install_fakes(client, monkeypatch, lambda *a, **k: hits, lambda messages: citation)
    response = _post_answer(
        client, engine, actors["teacher"], session_id,
        question="请说明记录", contest_id="contest-a",
    )
    assert response.status_code == 200
    assert response.json()["notifications"]["unused"] == 2


def test_answer_deduplicates_repeated_citations(client, engine, actors, monkeypatch):
    session_id = _new_session(client, engine, actors["teacher"])
    hit = _hit("a" * 32)
    citation = f"[review_id={hit['review_id']} dim=assumption]"
    _install_fakes(client, monkeypatch, lambda *a, **k: [hit], lambda messages: citation + citation)
    response = _post_answer(
        client, engine, actors["teacher"], session_id,
        question="请说明记录", contest_id="contest-a",
    )
    assert response.status_code == 200
    assert response.json()["refs"] == [{"review_id": hit["review_id"], "dimension_code": "assumption"}]


def test_answer_retries_model_once_then_persists(client, engine, actors, monkeypatch):
    session_id = _new_session(client, engine, actors["teacher"])
    hit = _hit("a" * 32)
    attempts = {"count": 0}

    def chat_fn(messages):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("first attempt")
        return f"结论 [review_id={hit['review_id']} dim=assumption]"

    _install_fakes(client, monkeypatch, lambda *a, **k: [hit], chat_fn)
    response = _post_answer(
        client, engine, actors["teacher"], session_id,
        question="请说明记录", contest_id="contest-a",
    )
    assert response.status_code == 200
    assert attempts["count"] == 2
    with Session(engine) as session:
        assert len(chat_store.load_messages(session, session_id)) == 2


def test_two_model_failures_return_502_without_persisting(client, engine, actors, monkeypatch):
    session_id = _new_session(client, engine, actors["teacher"])
    attempts = {"count": 0}

    def chat_fn(messages):
        attempts["count"] += 1
        raise RuntimeError("model failure")

    _install_fakes(client, monkeypatch, lambda *a, **k: [_hit("a" * 32)], chat_fn)
    response = _post_answer(
        client, engine, actors["teacher"], session_id,
        question="请说明记录", contest_id="contest-a",
    )
    assert response.status_code == 502
    assert attempts["count"] == 2
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(chat_models.ChatMessage)) == 0


def test_answer_prompt_caps_retrieval_context_at_eight(client, engine, actors, monkeypatch):
    session_id = _new_session(client, engine, actors["teacher"])
    hits = [_hit(f"{number:032x}") for number in range(10)]
    captured = {}

    def chat_fn(messages):
        captured["messages"] = messages
        return "根据片段无法回答。"

    _install_fakes(client, monkeypatch, lambda *a, **k: hits, chat_fn)
    response = _post_answer(
        client, engine, actors["teacher"], session_id,
        question="请说明记录", contest_id="contest-a",
    )
    assert response.status_code == 200
    assert captured["messages"][1]["content"].count("[1]") == 1
    assert sum(f"[{index}] review_id=" in captured["messages"][1]["content"] for index in range(1, 11)) == 8


def test_answer_system_prompt_contains_four_required_disciplines(client, engine, actors, monkeypatch):
    session_id = _new_session(client, engine, actors["teacher"])
    hit = _hit("a" * 32)
    captured = {}

    def chat_fn(messages):
        captured["messages"] = messages
        return "没有相关信息。"

    _install_fakes(client, monkeypatch, lambda *a, **k: [hit], chat_fn)
    response = _post_answer(
        client, engine, actors["teacher"], session_id,
        question="请说明记录", contest_id="contest-a",
    )
    assert response.status_code == 200
    system = captured["messages"][0]["content"]
    assert "不得编造" in system
    assert "review_id" in system
    assert "奖项" in system
    assert "300 字" in system
