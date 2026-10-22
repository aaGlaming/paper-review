from __future__ import annotations

import secrets
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import routes
from backend.app.api.app import create_app
from backend.app.auth import store as auth_store
from backend.app.auth.models import create_auth_schema
from backend.app.graph import review_graph
from backend.app.importing.models import Base as CatalogBase, Contest, Dimension, Rubric
from backend.app.report import models as report_models
from backend.app.report import artifact_models
from backend.app.report import store as report_store


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    create_auth_schema(engine)
    report_models.create_report_schema(engine)
    artifact_models.create_artifact_schema(engine)
    CatalogBase.metadata.create_all(engine)
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

    class Graph:
        values = {}

        def get_state(self, _config):
            return SimpleNamespace(values=self.values)

    graph = Graph()

    def fake_create_review(paper_text, review_id, *, graph):
        graph.values = {"sections": review_graph._parse_sections(paper_text)}
        return review_id

    monkeypatch.setattr(review_graph, "create_review", fake_create_review)
    monkeypatch.setattr(review_graph, "resume_review", lambda *_args, **_kwargs: {"status": "完成"})
    monkeypatch.setattr(routes, "_restore_snapshot", lambda *_args, **_kwargs: None)
    import importlib

    app_module = importlib.import_module("backend.app.api.app")

    monkeypatch.setattr(app_module, "model_available", lambda: False)

    def _override_session():
        with _scope() as session:
            yield session

    app = create_app()
    app.dependency_overrides[routes.get_session] = _override_session
    app.dependency_overrides[routes.get_graph] = lambda: graph
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _counts(engine):
    with Session(engine) as session:
        return {
            "review": session.scalar(select(func.count()).select_from(report_models.Review)) or 0,
            "review_session": session.scalar(select(func.count()).select_from(report_models.ReviewSession)) or 0,
            "review_dimension": session.scalar(select(func.count()).select_from(report_models.ReviewDimension)) or 0,
        }


def _seed_contest(engine, contest_id: str, *, rubric_status: str | None, dimensions: int = 5):
    with Session(engine) as session:
        session.add(
            Contest(
                contest_id=contest_id,
                year=2026,
                problem_code="X",
                title="测试赛题",
                statement="测试题面",
                status="published",
            )
        )
        session.flush()
        if rubric_status is not None:
            rubric_id = f"{contest_id}-rubric-v1"
            session.add(Rubric(rubric_id=rubric_id, contest_id=contest_id, version=1, status=rubric_status))
            session.flush()
            for index in range(dimensions):
                session.add(
                    Dimension(
                        dimension_id=f"{rubric_id}-d{index}",
                        rubric_id=rubric_id,
                        code=f"dimension-{index}",
                        name=f"维度 {index}",
                        weight=20,
                        evidence_prompts=[],
                        section_types=[],
                        bands=[],
                    )
                )
        session.commit()


def _save_pending_session(engine, review_id: str, contest_id: str):
    from backend.app.graph.review_graph import _parse_sections

    with Session(engine) as session:
        report_store.save_session(
            review_id,
            paper_text="# 摘要\n这是一段足够用于测试的正文。",
            sections=_parse_sections("# 摘要\n这是一段足够用于测试的正文。"),
            confirmed=False,
            status="待确认",
            contest_id=contest_id,
            user_id="test-default-user",
            session=session,
        )
        session.commit()


def test_empty_contest_id_still_creates_parse_session(client, engine):
    before = _counts(engine)

    response = client.post("/api/reviews", json={"paper_text": "# 摘要\n仅供解析的正文。", "contest_id": ""})

    assert response.status_code == 201
    assert response.json()["status"] == "待确认"
    assert _counts(engine) == {
        "review": before["review"] + 1,
        "review_session": before["review_session"] + 1,
        "review_dimension": before["review_dimension"],
    }


def test_empty_contest_parse_session_can_extract_artifacts_without_scoring(client, engine):
    response = client.post(
        "/api/reviews",
        json={
            "paper_text": "# 摘要\n本研究结果表明模型效果达到 22.4 s。",
            "contest_id": "",
        },
    )
    assert response.status_code == 201
    review_id = response.json()["review_id"]

    extracted = client.post(f"/api/reviews/{review_id}/artifacts/extract")

    assert extracted.status_code == 200
    assert extracted.json()["count"] > 0
    assert _counts(engine)["review"] == 1
    assert _counts(engine)["review_dimension"] == 0


def test_nonexistent_contest_is_rejected_before_review_or_session_write(client, engine):
    before = _counts(engine)

    response = client.post(
        "/api/reviews",
        json={"paper_text": "# 摘要\n这段正文足够长。", "contest_id": "missing-contest"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "该赛题不存在或没有已发布量规，无法开始评审"}
    assert _counts(engine) == before


def test_draft_only_rubric_is_rejected_without_database_writes(client, engine):
    _seed_contest(engine, "draft-only", rubric_status="draft")
    before = _counts(engine)

    response = client.post(
        "/api/reviews",
        json={"paper_text": "# 摘要\n这段正文足够长。", "contest_id": "draft-only"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "该赛题不存在或没有已发布量规，无法开始评审"}
    assert _counts(engine) == before


def test_published_rubric_without_dimensions_is_not_evaluable(client, engine):
    _seed_contest(engine, "empty-published-rubric", rubric_status="published", dimensions=0)
    before = _counts(engine)

    response = client.post(
        "/api/reviews",
        json={"paper_text": "# 摘要\n这段正文足够长。", "contest_id": "empty-published-rubric"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "该赛题不存在或没有已发布量规，无法开始评审"}
    assert _counts(engine) == before


def test_resume_without_published_rubric_returns_422_without_review_rows(client, engine):
    _seed_contest(engine, "resume-draft", rubric_status="draft")
    _save_pending_session(engine, "resume-no-rubric", "resume-draft")
    before = _counts(engine)

    response = client.post("/api/reviews/resume-no-rubric/resume", json={})

    assert response.status_code == 422
    assert response.json() == {"detail": "该赛题没有已发布量规，无法评分"}
    assert _counts(engine) == before


def test_resume_with_empty_published_rubric_is_rejected(client, engine):
    _seed_contest(engine, "resume-empty-published", rubric_status="published", dimensions=0)
    _save_pending_session(engine, "resume-empty-rubric", "resume-empty-published")
    before = _counts(engine)

    response = client.post("/api/reviews/resume-empty-rubric/resume", json={})

    assert response.status_code == 422
    assert response.json() == {"detail": "该赛题没有已发布量规，无法评分"}
    assert _counts(engine) == before


def test_resume_without_rubric_does_not_run_graph_or_deterministic_scoring(client, engine, monkeypatch):
    _save_pending_session(engine, "resume-no-rubric-no-fallback", "")
    calls = []

    def graph_called(*_args, **_kwargs):
        calls.append("graph")
        return {"status": "完成"}

    def fallback_called(*_args, **_kwargs):
        calls.append("fallback")
        return []

    monkeypatch.setattr(review_graph, "resume_review", graph_called)
    from backend.app.report import evaluation

    monkeypatch.setattr(evaluation, "deterministic_results", fallback_called)

    response = client.post("/api/reviews/resume-no-rubric-no-fallback/resume", json={})

    assert response.status_code == 422
    assert calls == []


def test_resume_with_published_rubric_keeps_scoring_path(client, engine):
    _seed_contest(engine, "published-topic", rubric_status="published")
    _save_pending_session(engine, "resume-published", "published-topic")

    response = client.post("/api/reviews/resume-published/resume", json={})

    assert response.status_code == 200
    assert response.json()["rubric_id"] == "published-topic-rubric-v1"
    assert response.json()["rubric_version"] == 1
    assert len(response.json()["dimensions"]) == 5
    assert _counts(engine)["review_dimension"] == 5


def test_unavailable_contest_rejections_write_review_rejected_events(client, engine, monkeypatch):
    events = []
    monkeypatch.setattr(routes, "log_event", lambda *args, **kwargs: events.append((args, kwargs)))
    client.post("/api/reviews", json={"paper_text": "# 摘要\n正文", "contest_id": "missing-log"})
    _save_pending_session(engine, "resume-log", "")
    client.post("/api/reviews/resume-log/resume", json={})

    assert [event[0][:2] for event in events] == [
        ("review", "review_rejected"),
        ("review", "review_rejected"),
    ]
    assert all("contest_id" in event[1] and "paper_text" not in event[1] for event in events)
