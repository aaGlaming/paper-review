from __future__ import annotations

import secrets
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import routes
from backend.app.api.app import create_app
from backend.app.auth import store as auth_store
from backend.app.auth.models import User, create_auth_schema
from backend.app.auth.security import hash_password
from backend.app.auth.token import issue_token
from backend.app.report import artifact_models, models as report_models, store as report_store


@pytest.fixture()
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

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
    app.dependency_overrides[routes.get_session] = _override_session
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


def _headers(engine, user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(engine, user_id)}"}


def _save_session(
    engine,
    review_id: str,
    user_id: str,
    text: str,
    *,
    confirmed: bool = True,
    contest_id: str = "",
):
    from backend.app.graph.review_graph import _parse_sections

    with Session(engine) as session:
        report_store.save_review(review_id, user_id=user_id, session=session)
        report_store.save_session(
            review_id,
            paper_text=text,
            sections=_parse_sections(text),
            confirmed=confirmed,
            contest_id=contest_id,
            user_id=user_id,
            session=session,
        )
        session.commit()


SAMPLE_TEXT = "# 摘要\n本文得到有效结果为 22.4 s，并提升了实验效果。\n\n## 参考文献\n[1] 参考文献条目。\n"


def test_first_extract_persists_artifacts_and_get_returns_ordinal_order(client, engine):
    owner = _user(engine, "extract-owner", "student")
    _save_session(engine, "extract-review", owner, SAMPLE_TEXT)

    response = client.post("/api/reviews/extract-review/artifacts/extract", headers=_headers(engine, owner))

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] > 0
    assert payload["by_type"]["claim"] >= 1
    fetched = client.get("/api/reviews/extract-review/artifacts", headers=_headers(engine, owner))
    assert fetched.status_code == 200
    assert [row["ordinal"] for row in fetched.json()] == sorted(row["ordinal"] for row in fetched.json())
    with Session(engine) as session:
        source = session.get(report_models.ReviewSession, "extract-review").paper_text
    for row in fetched.json():
        field = {"claim": "claim_text", "table": "table_markdown", "citation": "citation_text"}[row["artifact_type"]]
        assert source[row["char_start"] : row["char_end"]] == row[field]


def test_repeated_extract_replaces_existing_rows_idempotently(client, engine):
    owner = _user(engine, "extract-idempotent", "student")
    _save_session(engine, "extract-idempotent-review", owner, SAMPLE_TEXT)

    first = client.post("/api/reviews/extract-idempotent-review/artifacts/extract", headers=_headers(engine, owner)).json()
    second = client.post("/api/reviews/extract-idempotent-review/artifacts/extract", headers=_headers(engine, owner)).json()
    fetched = client.get("/api/reviews/extract-idempotent-review/artifacts", headers=_headers(engine, owner)).json()

    assert second["count"] == first["count"]
    assert second["by_type"] == first["by_type"]
    assert len(fetched) == first["count"]


def test_unconfirmed_sections_are_rejected_without_writing_artifacts(client, engine):
    owner = _user(engine, "extract-unconfirmed", "student")
    _save_session(
        engine,
        "extract-unconfirmed-review",
        owner,
        SAMPLE_TEXT,
        confirmed=False,
        contest_id="unconfirmed-bound-contest",
    )

    response = client.post("/api/reviews/extract-unconfirmed-review/artifacts/extract", headers=_headers(engine, owner))

    assert response.status_code == 409
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(artifact_models.ReviewArtifact)) == 0


def test_student_cannot_extract_another_users_review(client, engine):
    owner = _user(engine, "extract-private-owner", "student")
    other = _user(engine, "extract-private-other", "student")
    _save_session(engine, "extract-private-review", owner, SAMPLE_TEXT)

    response = client.post("/api/reviews/extract-private-review/artifacts/extract", headers=_headers(engine, other))

    assert response.status_code in (403, 404)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(artifact_models.ReviewArtifact)) == 0


def test_extract_without_paper_text_is_rejected(client, engine):
    owner = _user(engine, "extract-empty", "student")
    _save_session(engine, "extract-empty-review", owner, "   ")

    response = client.post("/api/reviews/extract-empty-review/artifacts/extract", headers=_headers(engine, owner))

    assert response.status_code == 422
    assert "正文" in response.text


def test_failed_replacement_rolls_back_the_previous_artifacts(client, engine, monkeypatch):
    owner = _user(engine, "extract-rollback", "student")
    _save_session(engine, "extract-rollback-review", owner, SAMPLE_TEXT)
    with Session(engine) as session:
        artifact_models.save_artifacts(
            "extract-rollback-review",
            [{
                "artifact_type": "claim",
                "ordinal": 0,
                "char_start": 5,
                "char_end": 31,
                "claim_text": "本文得到有效结果为 22.4 s，并提升了实验效果。",
                "section_type": "摘要",
            }],
            session=session,
        )
        session.commit()

    def fail_save(*_args, **_kwargs):
        raise ValueError("forced persistence validation failure")

    monkeypatch.setattr(artifact_models, "save_artifacts", fail_save)
    response = client.post("/api/reviews/extract-rollback-review/artifacts/extract", headers=_headers(engine, owner))

    assert response.status_code == 422
    with Session(engine) as session:
        rows = session.scalars(
            select(artifact_models.ReviewArtifact).where(
                artifact_models.ReviewArtifact.review_id == "extract-rollback-review"
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].claim_text == "本文得到有效结果为 22.4 s，并提升了实验效果。"


def test_extract_log_contains_counts_without_source_text(client, engine, monkeypatch):
    owner = _user(engine, "extract-log", "student")
    _save_session(engine, "extract-log-review", owner, SAMPLE_TEXT)
    captured = []
    monkeypatch.setattr(routes, "log_event", lambda *args, **kwargs: captured.append((args, kwargs)))

    response = client.post("/api/reviews/extract-log-review/artifacts/extract", headers=_headers(engine, owner))

    assert response.status_code == 200
    event, fields = captured[-1]
    assert event == ("importing", "artifacts_extracted")
    assert fields["review_id"] == "extract-log-review"
    assert fields["count"] == response.json()["count"]
    assert fields["by_type"] == response.json()["by_type"]
    assert "paper_text" not in fields
    assert SAMPLE_TEXT not in repr(fields)


def test_get_review_sections_ranges_are_contiguous_and_cover_the_source(client, engine):
    owner = _user(engine, "range-owner", "student")
    text = "# 摘要\n第一段。\n\n## 方法\n第二段。"
    _save_session(engine, "range-review", owner, text)

    response = client.get("/api/reviews/range-review", headers=_headers(engine, owner))

    assert response.status_code == 200
    body = response.json()
    assert body["sections_ranged"] is True
    sections = body["sections"]
    assert sections[0]["char_start"] == 0
    assert sections[-1]["char_end"] == len(text)
    assert all(left["char_end"] == right["char_start"] for left, right in zip(sections, sections[1:]))


def test_get_review_section_ranges_assign_each_heading_to_its_section(client, engine):
    owner = _user(engine, "range-content-owner", "student")
    text = "# 摘要\n第一段。\n\n## 方法\n第二段。"
    _save_session(engine, "range-content-review", owner, text)

    body = client.get("/api/reviews/range-content-review", headers=_headers(engine, owner)).json()

    for section in body["sections"]:
        span = text[section["char_start"] : section["char_end"]]
        heading = f"{'#' * section['level']} {section['title']}"
        assert span.startswith(heading)
        # The heading line belongs to this section; the parser strips surrounding body whitespace.
        assert span.split("\n", 1)[1].strip() == section["content"]


def test_get_review_degrades_when_confirmed_sections_do_not_match_source(client, engine):
    owner = _user(engine, "range-mismatch-owner", "student")
    _save_session(engine, "range-mismatch-review", owner, "# 摘要\n正文。")
    with Session(engine) as session:
        snapshot = session.get(report_models.ReviewSession, "range-mismatch-review")
        snapshot.sections = []
        session.commit()

    response = client.get("/api/reviews/range-mismatch-review", headers=_headers(engine, owner))

    assert response.status_code == 200
    assert response.json()["sections_ranged"] is False
    assert all("char_start" not in section and "char_end" not in section for section in response.json()["sections"])
