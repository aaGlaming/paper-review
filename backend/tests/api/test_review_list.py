"""P18 教师记录总览：过滤边界、分页、概览字段与聚合审计。"""

from __future__ import annotations

import json
import secrets
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.app import create_app
from backend.app.api.routes import get_session
from backend.app.auth import store as auth_store
from backend.app.auth.models import User, create_auth_schema
from backend.app.auth.security import hash_password
from backend.app.auth.token import issue_token
from backend.app.observability import logging as logging_mod
from backend.app.report import models as report_models
from backend.app.report import store as report_store


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_auth_schema(engine)
    report_models.create_report_schema(engine)
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


def _save(engine, review_id, user_id, *, contest="c1", created_at=None, **kwargs):
    with Session(engine) as session:
        row = report_store.save_review(
            review_id, user_id=user_id or "", contest_id=contest, session=session, **kwargs
        )
        if created_at is not None:
            session.get(report_models.Review, review_id).created_at = created_at
        session.commit()
        return row


@pytest.fixture()
def actors(engine):
    return {
        "a": _user(engine, "student-a", "student"),
        "b": _user(engine, "student-b", "student"),
        "teacher": _user(engine, "teacher-a", "teacher"),
    }


def test_student_list_only_contains_own_reviews(client, engine, actors):
    _save(engine, "a1", actors["a"])
    _save(engine, "b1", actors["b"])
    response = client.get("/api/reviews", headers=_headers(_token(engine, actors["a"])))
    assert response.status_code == 200
    assert [row["user_id"] for row in response.json()["reviews"]] == [actors["a"]]
    assert response.json()["scope"] == "own"


def test_student_explicit_other_user_id_is_ignored(client, engine, actors):
    _save(engine, "a1", actors["a"])
    _save(engine, "b1", actors["b"])
    response = client.get(
        f"/api/reviews?user_id={actors['b']}", headers=_headers(_token(engine, actors["a"]))
    )
    assert response.status_code == 200
    assert [row["user_id"] for row in response.json()["reviews"]] == [actors["a"]]


def test_teacher_list_contains_all_reviews(client, engine, actors):
    _save(engine, "a1", actors["a"])
    _save(engine, "b1", actors["b"])
    _save(engine, "null1", None)
    response = client.get("/api/reviews", headers=_headers(_token(engine, actors["teacher"])))
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["scope"] == "all"


def test_teacher_user_filter_returns_only_requested_owner(client, engine, actors):
    _save(engine, "a1", actors["a"])
    _save(engine, "b1", actors["b"])
    response = client.get(
        f"/api/reviews?user_id={actors['b']}",
        headers=_headers(_token(engine, actors["teacher"])),
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [row["user_id"] for row in response.json()["reviews"]] == [actors["b"]]


def test_teacher_empty_user_filter_returns_unowned_reviews(client, engine, actors):
    _save(engine, "a1", actors["a"])
    _save(engine, "null1", None)
    response = client.get(
        "/api/reviews?user_id=", headers=_headers(_token(engine, actors["teacher"]))
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["reviews"][0]["user_id"] is None


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_contest_filter_applies_for_both_roles(client, engine, actors, role):
    viewer = actors["a"] if role == "student" else actors["teacher"]
    _save(engine, "c1-a", actors["a"], contest="c1")
    _save(engine, "c2-a", actors["a"], contest="c2")
    _save(engine, "c1-b", actors["b"], contest="c1")
    response = client.get(
        "/api/reviews?contest_id=c1", headers=_headers(_token(engine, viewer))
    )
    assert response.status_code == 200
    assert all(row["contest_id"] == "c1" for row in response.json()["reviews"])
    assert response.json()["total"] == (1 if role == "student" else 2)


def test_pagination_keeps_total_and_changes_page(client, engine, actors):
    for i in range(3):
        _save(engine, f"r{i}", actors["a"])
    token = _token(engine, actors["a"])
    first = client.get("/api/reviews?page=1&page_size=1", headers=_headers(token)).json()
    second = client.get("/api/reviews?page=2&page_size=1", headers=_headers(token)).json()
    assert len(first["reviews"]) == 1
    assert first["total"] == second["total"] == 3
    assert first["reviews"][0]["review_id"] != second["reviews"][0]["review_id"]


def test_page_size_clamps_and_page_zero_is_validation_error(client, engine, actors):
    token = _token(engine, actors["teacher"])
    big = client.get("/api/reviews?page_size=1000", headers=_headers(token))
    assert big.status_code == 200
    assert big.json()["page_size"] == 100
    assert client.get("/api/reviews?page=0", headers=_headers(token)).status_code == 422


def test_bands_summary_contains_all_five_dimensions(client, engine, actors):
    codes = ["assumption", "method", "evidence", "analysis", "conclusion"]
    bands = ["基本", "较好", "充分", "良好", "基本"]
    _save(
        engine, "five-d", actors["a"],
        dimensions=[{"dimension_code": code, "band": band} for code, band in zip(codes, bands)],
    )
    response = client.get("/api/reviews", headers=_headers(_token(engine, actors["a"])))
    assert response.json()["reviews"][0]["bands"] == dict(zip(codes, bands))


def test_finding_total_counts_only_finding_items(client, engine, actors):
    _save(
        engine, "changes", actors["a"],
        change_list=[
            {"finding_kind": "conflict", "text": "x"},
            {"dimension_code": "assumption", "text": "y"},
            {"dimension_code": "method", "text": "z"},
        ],
    )
    response = client.get("/api/reviews", headers=_headers(_token(engine, actors["a"])))
    assert response.json()["reviews"][0]["finding_total"] == 1


def test_owner_username_is_null_for_unowned_and_username_for_owned(client, engine, actors):
    _save(engine, "owned", actors["a"])
    _save(engine, "unowned", None)
    response = client.get("/api/reviews", headers=_headers(_token(engine, actors["teacher"])))
    rows = {row["review_id"]: row for row in response.json()["reviews"]}
    assert rows["owned"]["owner_username"] == "student-a"
    assert rows["unowned"]["owner_username"] is None


def test_same_created_at_orders_review_id_ascending(client, engine, actors):
    from datetime import datetime

    stamp = datetime(2026, 1, 1, 12, 0, 0)
    _save(engine, "z-id", actors["a"], created_at=stamp)
    _save(engine, "a-id", actors["a"], created_at=stamp)
    response = client.get("/api/reviews", headers=_headers(_token(engine, actors["a"])))
    assert [row["review_id"] for row in response.json()["reviews"]] == ["a-id", "z-id"]


def _audit_texts(log_dir):
    return "\n".join(path.read_text(encoding="utf-8") for path in log_dir.rglob("*.log"))


def test_teacher_detail_audits_other_but_not_own(client, engine, actors, tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("LOG_DISABLED", "0")
    logging_mod.reset_logging_for_tests()
    try:
        _save(engine, "owned", actors["teacher"])
        _save(engine, "other", actors["a"])
        token = _token(engine, actors["teacher"])
        assert client.get("/api/reviews/other", headers=_headers(token)).status_code == 200
        assert _audit_texts(tmp_path / "audit").count('"event":"record_viewed"') == 1
        logging_mod.reset_logging_for_tests()
        assert client.get("/api/reviews/owned", headers=_headers(token)).status_code == 200
        assert _audit_texts(tmp_path / "audit").count('"event":"record_viewed"') == 1
    finally:
        logging_mod.reset_logging_for_tests()


def test_teacher_list_audits_once_when_page_has_others_student_does_not(
    client, engine, actors, tmp_path, monkeypatch
):
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("LOG_DISABLED", "0")
    logging_mod.reset_logging_for_tests()
    try:
        _save(engine, "a1", actors["a"])
        _save(engine, "b1", actors["b"])
        teacher_response = client.get(
            "/api/reviews", headers=_headers(_token(engine, actors["teacher"]))
        )
        assert teacher_response.status_code == 200
        teacher_logs = _audit_texts(tmp_path / "audit")
        assert teacher_logs.count('"event":"records_listed"') == 1
        event = next(
            json.loads(line) for path in (tmp_path / "audit").rglob("*.log")
            for line in path.read_text(encoding="utf-8").splitlines()
            if '"event":"records_listed"' in line
        )
        assert event["others"] >= 1
        assert event["scope"] == "all"
        logging_mod.reset_logging_for_tests()
        student_response = client.get(
            "/api/reviews", headers=_headers(_token(engine, actors["a"]))
        )
        assert student_response.status_code == 200
        assert _audit_texts(tmp_path / "audit").count('"event":"records_listed"') == 1
    finally:
        logging_mod.reset_logging_for_tests()


def test_teacher_owner_owned_filter_returns_all_owned_reviews(client, engine, actors):
    _save(engine, "owned-a", actors["a"])
    _save(engine, "owned-b", actors["b"])
    _save(engine, "orphan", None)
    response = client.get(
        "/api/reviews?owner=owned", headers=_headers(_token(engine, actors["teacher"]))
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert all(row["user_id"] is not None for row in response.json()["reviews"])


def test_owner_orphan_filter_and_student_ownership_boundary(client, engine, actors):
    _save(engine, "owned-a", actors["a"])
    _save(engine, "owned-b", actors["b"])
    _save(engine, "orphan", None)
    teacher_response = client.get(
        "/api/reviews?owner=orphan", headers=_headers(_token(engine, actors["teacher"]))
    )
    assert teacher_response.status_code == 200
    assert teacher_response.json()["total"] == 1
    assert all(row["user_id"] is None for row in teacher_response.json()["reviews"])

    student_response = client.get(
        "/api/reviews?owner=orphan", headers=_headers(_token(engine, actors["a"]))
    )
    assert student_response.status_code == 200
    assert student_response.json()["total"] == 1
    assert [row["user_id"] for row in student_response.json()["reviews"]] == [actors["a"]]


def test_archived_review_detail_includes_saved_sections(client, engine, actors):
    sections = [{
        "title": "正文段落",
        "section_type": "body",
        "level": 1,
        "content": "用于定位的正文内容。",
    }]
    _save(engine, "archive-with-sections", actors["teacher"], dimensions=[])
    with Session(engine) as session:
        report_store.save_session(
            "archive-with-sections",
            paper_text=sections[0]["content"],
            sections=sections,
            user_id=actors["teacher"],
            session=session,
        )
        session.commit()

    response = client.get(
        "/api/reviews/archive-with-sections",
        headers=_headers(_token(engine, actors["teacher"])),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sections"]
    assert body["sections"][0]["title"] == "正文段落"
    assert body["sections"][0]["content"] == "用于定位的正文内容。"
    assert body["review_id"] == "archive-with-sections"
    assert body["dimensions"] == []


def test_archived_review_detail_without_snapshot_returns_empty_sections(client, engine, actors):
    _save(
        engine,
        "archive-without-sections",
        actors["teacher"],
        dimensions=[{"dimension_code": "assumption", "band": "基本", "quote": "原句"}],
        change_list=[{"kind": "建议", "dimension_code": "assumption", "action": "保留记录"}],
    )

    response = client.get(
        "/api/reviews/archive-without-sections",
        headers=_headers(_token(engine, actors["teacher"])),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sections"] == []
    assert body["review_id"] == "archive-without-sections"
    assert body["dimensions"][0]["quote"] == "原句"
    assert body["change_list"][0]["action"] == "保留记录"
