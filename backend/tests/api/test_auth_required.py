"""评审四个读写端点必须登录，并按真实角色执行归属检查。"""

from __future__ import annotations

import secrets
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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


def _make_user(engine, username, role):
    with Session(engine) as session:
        row = auth_store.create_user(
            session,
            username=username,
            email=f"{username}@example.com",
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


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anonymous
def test_create_review_requires_authentication(client):
    response = client.post("/api/reviews", json={"paper_text": "x", "contest_id": "c1"})
    assert response.status_code == 401
    assert response.json() == {"detail": "未登录或登录已过期"}


@pytest.mark.anonymous
def test_resume_review_requires_authentication(client):
    response = client.post("/api/reviews/r1/resume", json={})
    assert response.status_code == 401
    assert response.json() == {"detail": "未登录或登录已过期"}


@pytest.mark.anonymous
def test_get_review_requires_authentication(client):
    response = client.get("/api/reviews/r1")
    assert response.status_code == 401
    assert response.json() == {"detail": "未登录或登录已过期"}


@pytest.mark.anonymous
def test_get_agent_steps_requires_authentication(client):
    response = client.get("/api/reviews/r1/agent-steps")
    assert response.status_code == 401
    assert response.json() == {"detail": "未登录或登录已过期"}


def test_student_create_review_persists_student_owner(client, engine):
    # 请求带真实学生 token，因此身份注入 fixture 会走 _resolve 的真实校验路径。
    student = _make_user(engine, "stu001", "student")
    response = client.post(
        "/api/reviews",
        json={"paper_text": "第一章\n\n研究内容。", "contest_id": "c1"},
        headers=_auth(_token(engine, student)),
    )
    assert response.status_code == 201, response.text
    review_id = response.json()["review_id"]
    with Session(engine) as session:
        assert session.get(report_models.ReviewSession, review_id).user_id == student


def test_student_reads_own_review_but_not_anothers(client, engine):
    # 两次请求都带真实学生 token，因此 fixture 不替换真实鉴权结果。
    student = _make_user(engine, "stu001", "student")
    other = _make_user(engine, "stu002", "student")
    with Session(engine) as session:
        report_store.save_session("mine", paper_text="x", user_id=student, session=session)
        report_store.save_review(
            "theirs", contest_id="c1", rubric_id="r1", dimensions={},
            change_list=[], user_id=other, session=session,
        )
        session.commit()
    token = _token(engine, student)
    own = client.get("/api/reviews/mine", headers=_auth(token))
    theirs = client.get("/api/reviews/theirs", headers=_auth(token))
    assert own.status_code == 200
    assert theirs.status_code == 404
    assert theirs.json() == {"detail": "找不到评审记录"}


def test_teacher_reads_ownerless_review_student_does_not(client, engine):
    # 两个请求均带真实身份 token，验证角色权限而非测试默认身份。
    student = _make_user(engine, "stu001", "student")
    teacher = _make_user(engine, "tea001", "teacher")
    with Session(engine) as session:
        report_store.save_session("legacy", paper_text="x", user_id="", session=session)
        session.commit()
    denied = client.get("/api/reviews/legacy", headers=_auth(_token(engine, student)))
    allowed = client.get("/api/reviews/legacy", headers=_auth(_token(engine, teacher)))
    assert denied.status_code == 404
    assert denied.json() == {"detail": "找不到评审记录"}
    assert allowed.status_code == 200


def test_tampered_token_has_same_401_message(client, engine):
    # 带签名被篡改的真实 token，身份注入 fixture 必须保留真实 401。
    student = _make_user(engine, "stu001", "student")
    token = _token(engine, student)
    head, body, signature = token.split(".")
    altered = f"{head}.{body}.{'A' if signature[-1] != 'A' else 'B'}{signature[1:]}"
    response = client.get("/api/reviews/r1", headers=_auth(altered))
    assert response.status_code == 401
    assert response.json() == {"detail": "未登录或登录已过期"}
