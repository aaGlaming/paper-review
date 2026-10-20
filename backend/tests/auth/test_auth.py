"""P17 账号体系测试：sqlite 内存库 + create_auth_schema，不连真 MySQL。

auth 接口走 `auth.store.session_scope_cm`（模块级上下文管理器），测试用
monkeypatch 把它换成绑定 sqlite 内存库的版本；`AUTH_SECRET` 用 monkeypatch
设 64 位随机值，不进任何夹具文件。
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.app import create_app
from backend.app.auth import store as auth_store
from backend.app.auth.models import Permission, User, create_auth_schema
from backend.app.auth.permissions import DEFAULT_PERMISSIONS
from backend.app.auth.security import hash_password, verify_password
from backend.app.auth.token import TokenError, decode_token, issue_token
from backend.app.observability import metrics


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_auth_schema(engine)
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
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _register(client, username="stu001", email="s1@example.com", password="abc12345"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "display_name": ""},
    )


def _login(client, username="stu001", password="abc12345"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_register_ok_returns_201_and_scrypt_hash(client, engine):
    assert _register(client).status_code == 201
    with Session(engine) as session:
        row = session.scalars(select(User)).one()
        assert row.password_hash.startswith("scrypt$")
        assert row.password_hash != "abc12345"
        assert row.role == "student"
        assert len(auth_store.list_permissions(session, row.user_id)) == 3


def test_same_password_hashes_differ(client, engine):
    assert _register(client, username="u01", email="u1@example.com").status_code == 201
    assert _register(client, username="u02", email="u2@example.com").status_code == 201
    with Session(engine) as session:
        hashes = [row.password_hash for row in session.scalars(select(User)).all()]
        assert len(hashes) == 2
        assert hashes[0] != hashes[1]
        assert all(verify_password("abc12345", item) for item in hashes)


def test_duplicate_username_and_email_share_same_409(client):
    assert _register(client).status_code == 201
    dup_name = _register(client, email="other@example.com")
    dup_mail = _register(client, username="other")
    assert dup_name.status_code == 409
    assert dup_mail.status_code == 409
    assert dup_name.json()["detail"] == dup_mail.json()["detail"]


def test_weak_passwords_rejected_422(client):
    assert _register(client, password="abc12").status_code == 422
    assert _register(client, username="u2", email="u2@example.com", password="abcdefgh").status_code == 422
    assert _register(client, username="u3", email="u3@example.com", password="12345678").status_code == 422


def test_login_ok_returns_v1_token(client):
    _register(client)
    response = _login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token"].split(".")[0] == "v1"
    assert body["role"] == "student"
    assert sorted(body["permissions"]) == sorted(DEFAULT_PERMISSIONS["student"])


def test_login_failures_indistinguishable(client):
    _register(client)
    bad_password = _login(client, password="wrong1234")
    unknown_user = _login(client, username="nobody", password="wrong1234")
    assert bad_password.status_code == 401
    assert unknown_user.status_code == 401
    assert bad_password.json() == unknown_user.json()


@pytest.mark.anonymous
def test_me_needs_bearer_token(client):
    _register(client)
    token = _login(client).json()["token"]
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer x"}).status_code == 401
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "stu001"


def test_tampered_signature_rejected(client, monkeypatch):
    _register(client)
    token = _login(client).json()["token"]
    head, body, sig = token.split(".")
    tampered = f"{head}.{body}.{'A' if sig[-1] != 'A' else 'B'}{sig[1:]}"
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401
    with pytest.raises(TokenError) as exc_info:
        decode_token(tampered)
    assert exc_info.value.reason == "bad_signature"


def test_expired_token_rejected(client, monkeypatch, engine):
    _register(client)
    with Session(engine) as session:
        row = session.scalars(select(User)).one()
        user_id, role, password_hash = row.user_id, row.role, row.password_hash
    expired = issue_token(user_id, role, password_hash, ttl_s=-10)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    with pytest.raises(TokenError) as exc_info:
        decode_token(expired)
    assert exc_info.value.reason == "expired"


def test_password_change_invalidates_old_token(client, engine):
    _register(client)
    old_token = _login(client).json()["token"]
    with Session(engine) as session:
        row = session.scalars(select(User)).one()
        row.password_hash = hash_password("newpass99")
        session.commit()
        user_id = row.user_id
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert response.status_code == 401
    with Session(engine) as session:
        row = session.get(User, user_id)
        assert verify_password("newpass99", row.password_hash)
        assert not verify_password("abc12345", row.password_hash)


def test_auth_logs_contain_no_secrets(client, engine, tmp_path, monkeypatch):
    import os

    from backend.app.observability import logging as logging_mod

    log_dir = tmp_path / "logs"
    monkeypatch.setenv("LOG_DIR", str(log_dir))
    monkeypatch.setenv("LOG_DISABLED", "0")
    logging_mod.reset_logging_for_tests()
    _register(client)
    token = _login(client).json()["token"]
    client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    secret = os.environ.get("AUTH_SECRET", "")
    texts = [path.read_text(encoding="utf-8") for path in log_dir.rglob("*.log")]
    combined = "\n".join(texts)
    assert combined
    assert "abc12345" not in combined
    assert "password_hash" not in combined
    assert "scrypt$" not in combined
    assert token not in combined
    assert secret not in combined
    assert "Authorization" not in combined
    logging_mod.reset_logging_for_tests()


def test_inc_auth_reflected_in_metrics(client):
    metrics.reset_metrics_for_tests()
    _register(client)
    _login(client)
    _login(client, password="wrong1234")
    text = client.get("/metrics").text
    assert 'paper_review_auth_total{result="success"} 1' in text
    assert 'paper_review_auth_total{result="failure"} 1' in text


def test_create_auth_schema_is_idempotent(engine):
    create_auth_schema(engine)
    create_auth_schema(engine)
    with Session(engine) as session:
        session.add(User(user_id="u", username="u", email="u@e.com", password_hash="x"))
        session.commit()
        assert session.get(User, "u") is not None
