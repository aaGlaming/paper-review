"""P17 第二份：权限门卫与评审归属测试。

同一个 sqlite 内存 engine 上先 create_auth_schema 再 create_report_schema
（两表共存本身就是一条隐含要求）。auth 会话走 monkeypatch，
routes 的 get_session 用 dependency_overrides 换成同一个 engine 的会话。
"""

from __future__ import annotations

import secrets
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import routes as routes_mod
from backend.app.api.app import create_app
from backend.app.api.routes import get_session
from backend.app.auth import store as auth_store
from backend.app.auth.models import User, create_auth_schema
from backend.app.auth.security import hash_password
from backend.app.auth.token import issue_token
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


def _make_user(engine, username, role, email=None):
    with Session(engine) as session:
        row = auth_store.create_user(
            session,
            username=username,
            email=email or f"{username}@example.com",
            password_hash=hash_password("abc12345"),
            display_name="",
            role=role,
        )
        session.commit()
        return row.user_id


def _token(engine, user_id):
    with Session(engine) as session:
        row = session.get(User, user_id)
        return issue_token(row.user_id, row.role, row.password_hash)


@pytest.fixture()
def student(engine):
    return _make_user(engine, "stu001", "student")


@pytest.fixture()
def student2(engine):
    return _make_user(engine, "stu002", "student")


@pytest.fixture()
def teacher(engine):
    return _make_user(engine, "tea001", "teacher", email="teacher@example.com")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_student_list_users_403_without_permission_code(client, engine, student):
    response = client.get("/api/users", headers=_auth(_token(engine, student)))
    assert response.status_code == 403
    assert response.json() == {"detail": "没有权限执行该操作"}
    assert "review:read:all" not in response.text


def test_student_list_users_writes_audit_permission_denied(client, engine, student, tmp_path, monkeypatch):
    from backend.app.observability import logging as logging_mod

    log_dir = tmp_path / "logs"
    monkeypatch.setenv("LOG_DIR", str(log_dir))
    monkeypatch.setenv("LOG_DISABLED", "0")
    logging_mod.reset_logging_for_tests()
    try:
        response = client.get("/api/users", headers=_auth(_token(engine, student)))
        assert response.status_code == 403
        texts = [path.read_text(encoding="utf-8") for path in log_dir.rglob("*.log")]
        combined = "\n".join(texts)
        assert "permission_denied" in combined
        assert student in combined
    finally:
        logging_mod.reset_logging_for_tests()


def test_teacher_list_users_200_without_password_hash(client, engine, teacher, student):
    response = client.get("/api/users", headers=_auth(_token(engine, teacher)))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert len(body["users"]) >= 2
    raw = response.text
    assert "password_hash" not in raw
    assert "scrypt$" not in raw


def test_list_users_email_masked(client, engine, teacher, student):
    response = client.get("/api/users", headers=_auth(_token(engine, teacher)))
    assert response.status_code == 200
    masked = [item["email_masked"] for item in response.json()["users"]]
    assert "s***@example.com" in masked
    assert "t***@example.com" in masked
    assert "stu001@example.com" not in response.text


def test_list_users_pagination_clamps_page_size(client, engine, teacher, student):
    token = _token(engine, teacher)
    one = client.get("/api/users?page=1&page_size=1", headers=_auth(token))
    assert one.status_code == 200
    assert len(one.json()["users"]) == 1
    assert one.json()["total"] >= 2
    big = client.get("/api/users?page=1&page_size=1000", headers=_auth(token))
    assert big.status_code == 200
    assert big.json()["page_size"] == 100


@pytest.mark.anonymous
def test_list_users_without_or_expired_token_401(client, engine, teacher):
    assert client.get("/api/users").status_code == 401
    with Session(engine) as session:
        row = session.get(User, teacher)
        expired = issue_token(row.user_id, row.role, row.password_hash, ttl_s=-10)
    response = client.get("/api/users", headers=_auth(expired))
    assert response.status_code == 401
    assert response.json() == {"detail": "未登录或登录已过期"}


def test_student_gets_own_detail_200(client, engine, student):
    response = client.get(f"/api/users/{student}", headers=_auth(_token(engine, student)))
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "stu001"
    assert body["email"] == "stu001@example.com"
    assert "password_hash" not in response.text


def test_student_gets_other_detail_404_identical_to_missing(client, engine, student, student2):
    mine = client.get(f"/api/users/{student2}", headers=_auth(_token(engine, student)))
    assert mine.status_code == 404
    ghost = client.get("/api/users/no-such-user", headers=_auth(_token(engine, student)))
    assert ghost.status_code == 404
    assert mine.json() == ghost.json()
    assert mine.content == ghost.content


def test_teacher_gets_other_detail_200_with_permissions_and_reviews(
    client, engine, teacher, student
):
    with Session(engine) as session:
        report_store.save_review(
            "r-teacher-sees", contest_id="c1", rubric_id="r1",
            dimensions={}, change_list=[], user_id=student, session=session,
        )
        session.commit()
    response = client.get(f"/api/users/{student}", headers=_auth(_token(engine, teacher)))
    assert response.status_code == 200
    body = response.json()
    assert "review:create" in body["permissions"]
    assert any(item["review_id"] == "r-teacher-sees" for item in body["reviews"])


def test_create_review_with_token_stores_owner(client, engine, student):
    response = client.post(
        "/api/reviews",
        json={"paper_text": "第一章\n\n本研究以板凳龙为对象。", "contest_id": "c1"},
        headers=_auth(_token(engine, student)),
    )
    assert response.status_code == 201, response.text
    review_id = response.json()["review_id"]
    # 创建只写会话快照（落 review 表要等 resume），归属先断快照。
    with Session(engine) as session:
        snapshot = session.get(report_models.ReviewSession, review_id)
        assert snapshot.user_id == student
    # save_review 的 user_id 落库路径（resume 调它）：直写一条断 review 表。
    with Session(engine) as session:
        report_store.save_review(
            "r-owned-by-student", contest_id="c1", rubric_id="r1",
            dimensions={}, change_list=[], user_id=student, session=session,
        )
        session.commit()
        row = session.get(report_models.Review, "r-owned-by-student")
        assert row.user_id == student


@pytest.mark.anonymous
def test_create_review_without_token_401(client, engine):
    response = client.post(
        "/api/reviews",
        json={"paper_text": "第一章\n\n本研究以板凳龙为对象。", "contest_id": "c1"},
    )
    assert response.status_code == 401


def test_save_session_empty_user_id_stores_null(engine):
    with Session(engine) as session:
        report_store.save_session(
            "r-null-owner", paper_text="x", user_id="", session=session
        )
        session.commit()
        snapshot = session.get(report_models.ReviewSession, "r-null-owner")
        assert snapshot.user_id is None


def test_student_cannot_read_other_review_but_teacher_can(client, engine, student, student2, teacher):
    with Session(engine) as session:
        report_store.save_review(
            "r-owned", contest_id="c1", rubric_id="r1",
            dimensions={}, change_list=[], user_id=student2, session=session,
        )
        session.commit()
    other = client.get("/api/reviews/r-owned", headers=_auth(_token(engine, student)))
    assert other.status_code == 404
    missing = client.get("/api/reviews/no-such-review", headers=_auth(_token(engine, student)))
    assert missing.status_code == 404
    assert other.json() == missing.json()
    ok = client.get("/api/reviews/r-owned", headers=_auth(_token(engine, teacher)))
    assert ok.status_code == 200
    assert ok.json()["review_id"] == "r-owned"


def test_ownerless_review_visible_to_teacher_only(client, engine, student, teacher):
    with Session(engine) as session:
        report_store.save_review(
            "r-legacy", contest_id="c1", rubric_id="r1",
            dimensions={}, change_list=[], session=session,
        )
        session.commit()
        assert session.get(report_models.Review, "r-legacy").user_id is None
    denied = client.get("/api/reviews/r-legacy", headers=_auth(_token(engine, student)))
    assert denied.status_code == 404
    allowed = client.get("/api/reviews/r-legacy", headers=_auth(_token(engine, teacher)))
    assert allowed.status_code == 200
