from __future__ import annotations

import secrets
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.app import create_app
from backend.app.api.routes import get_session
from backend.app.auth import store as auth_store
from backend.app.auth.models import User, create_auth_schema
from backend.app.auth.security import hash_password
from backend.app.auth.token import issue_token
from backend.app.report import artifact_models, models as report_models, store as report_store


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    create_auth_schema(engine)
    report_models.create_report_schema(engine)
    artifact_models.create_artifact_schema(engine)
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


def _user(engine, username: str, role: str) -> str:
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


def _token(engine, user_id: str) -> str:
    with Session(engine) as session:
        row = session.get(User, user_id)
        return issue_token(row.user_id, row.role, row.password_hash)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _save_review(engine, review_id: str, user_id: str):
    with Session(engine) as session:
        report_store.save_review(review_id, user_id=user_id, session=session)
        session.commit()


def _claim(ordinal: int, text: str = "A supported claim.") -> dict[str, object]:
    return {
        "artifact_type": "claim",
        "ordinal": ordinal,
        "char_start": ordinal,
        "char_end": ordinal + 5,
        "claim_text": text,
        "section_type": "摘要",
    }


def test_create_artifact_schema_is_idempotent_and_preserves_rows(engine):
    _save_review(engine, "review-idempotent", "owner")
    with Session(engine) as session:
        artifact_models.save_artifacts("review-idempotent", [_claim(0)], session=session)
        session.commit()

    artifact_models.create_artifact_schema(engine)
    artifact_models.create_artifact_schema(engine)

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(artifact_models.ReviewArtifact)) == 1


def test_existing_review_without_artifacts_returns_empty_array(client, engine):
    owner = _user(engine, "student-empty", "student")
    _save_review(engine, "review-empty", owner)

    response = client.get(
        "/api/reviews/review-empty/artifacts",
        headers=_headers(_token(engine, owner)),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_save_rejects_unknown_artifact_type(engine):
    with Session(engine) as session, pytest.raises(ValueError, match="artifact_type"):
        artifact_models.save_artifacts(
            "review-invalid",
            [{"artifact_type": "summary", "ordinal": 0, "char_start": 0, "char_end": 1}],
            session=session,
        )


def test_save_rejects_missing_type_specific_field(engine):
    with Session(engine) as session, pytest.raises(ValueError, match="claim_text"):
        artifact_models.save_artifacts(
            "review-missing-field",
            [{"artifact_type": "claim", "ordinal": 0, "char_start": 0, "char_end": 1}],
            session=session,
        )


def test_deleting_review_cascades_to_artifacts(engine):
    _save_review(engine, "review-cascade", "owner")
    with Session(engine) as session:
        artifact_models.save_artifacts("review-cascade", [_claim(0)], session=session)
        session.commit()
        session.delete(session.get(report_models.Review, "review-cascade"))
        session.commit()
        assert session.scalar(select(func.count()).select_from(artifact_models.ReviewArtifact)) == 0


def test_artifacts_return_in_ordinal_order(client, engine):
    owner = _user(engine, "student-order", "student")
    _save_review(engine, "review-order", owner)
    with Session(engine) as session:
        artifact_models.save_artifacts(
            "review-order", [_claim(9, "Later claim."), _claim(2, "Earlier claim.")], session=session
        )
        session.commit()

    response = client.get(
        "/api/reviews/review-order/artifacts",
        headers=_headers(_token(engine, owner)),
    )

    assert response.status_code == 200
    assert [item["ordinal"] for item in response.json()] == [2, 9]


def test_teacher_can_read_any_review_but_student_cannot_read_others(client, engine):
    owner = _user(engine, "student-owner", "student")
    other = _user(engine, "student-other", "student")
    teacher = _user(engine, "teacher-reader", "teacher")
    _save_review(engine, "review-private", owner)

    student_response = client.get(
        "/api/reviews/review-private/artifacts",
        headers=_headers(_token(engine, other)),
    )
    teacher_response = client.get(
        "/api/reviews/review-private/artifacts",
        headers=_headers(_token(engine, teacher)),
    )

    assert student_response.status_code == 404
    assert teacher_response.status_code == 200
    assert teacher_response.json() == []
