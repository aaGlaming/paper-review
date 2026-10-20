"""P19 评审记录聚合与教研摘要：数字由数据库统计，模型只负责表达。"""

from __future__ import annotations

import secrets
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
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
            session, username=username, email=f"{username}@example.com",
            password_hash=hash_password("test-password-123"), role=role,
        )
        session.commit()
        return row.user_id


@pytest.fixture()
def actors(engine):
    return {
        "student": _create_user(engine, "analytics-student", "student"),
        "teacher": _create_user(engine, "analytics-teacher", "teacher"),
        "teacher2": _create_user(engine, "analytics-teacher2", "teacher"),
    }


def _headers(engine, user_id: str) -> dict[str, str]:
    with Session(engine) as session:
        row = session.get(User, user_id)
        token = issue_token(row.user_id, row.role, row.password_hash)
    return {"Authorization": f"Bearer {token}"}


def _save(
    session: Session,
    review_id: str,
    *,
    contest_id: str = "contest-a",
    user_id: str = "student-a",
    dimensions=None,
    changes=None,
):
    return report_store.save_review(
        review_id, contest_id=contest_id, user_id=user_id,
        dimensions=dimensions or [], change_list=changes or [], session=session,
    )


def _dim(band: str, quote: str | None = None, dimension_code: str = "assumption"):
    return {"dimension_code": dimension_code, "band": band, "quote": quote}


def _hit(review_id: str, dimension_code: str = "assumption") -> dict[str, str]:
    return {
        "review_id": review_id,
        "dimension_code": dimension_code,
        "parent_id": f"rr-{review_id}-{dimension_code}",
        "content": "【维度】assumption 【档位】基本\n【原句】证据片段",
    }


def _install_fakes(client, search_fn, chat_fn):
    from backend.app.api import chat_routes

    app = client.app
    app.dependency_overrides[chat_routes.get_search_fn] = lambda: search_fn
    app.dependency_overrides[chat_routes.get_chat_fn] = lambda: chat_fn


def test_compare_bands_filters_to_requested_contest(engine):
    from backend.app.chat.analytics import compare_bands

    with Session(engine) as session:
        _save(session, "a1", dimensions=[_dim("基本")])
        _save(session, "b1", contest_id="contest-b", dimensions=[_dim("充分")])
        result = compare_bands(session, contest_id="contest-a")
    assert result["reviews"] == 1
    assert result["bands"] == [{
        "dimension_code": "assumption", "counts": {"基本": 1},
        "insufficient": 0, "reviews": 1,
    }]


def test_compare_bands_counts_owned_students_and_orphans_separately(engine):
    from backend.app.chat.analytics import compare_bands

    with Session(engine) as session:
        _save(session, "a1", user_id="student-a", dimensions=[_dim("基本")])
        _save(session, "a2", user_id="student-a", dimensions=[_dim("充分")])
        _save(session, "a3", user_id="", dimensions=[_dim("基本")])
        result = compare_bands(session, contest_id="contest-a")
    assert result["students"] == 1
    assert result["orphan_reviews"] == 1
    assert result["reviews"] == 3


def test_compare_bands_normalizes_both_insufficient_band_labels(engine):
    from backend.app.chat.analytics import compare_bands

    with Session(engine) as session:
        _save(session, "short", dimensions=[_dim("不足")])
        _save(session, "explicit", dimensions=[_dim("证据不足")])
        result = compare_bands(session, contest_id="contest-a")
    assert result["insufficient_total"] == 2
    assert result["bands"][0]["insufficient"] == 2


def test_conflict_kinds_and_finding_total_exclude_dimension_entries(engine):
    from backend.app.chat.analytics import summarize_conflicts

    changes = [
        {"kind": "数字冲突", "finding_kind": "conflict", "target": "指标甲"},
        {"kind": "表述", "finding_kind": "wording", "target": "指标乙"},
        {"kind": "维度调整", "dimension_code": "assumption", "text": "档位变化"},
    ]
    with Session(engine) as session:
        _save(session, "a1", changes=changes)
        result = summarize_conflicts(session, contest_id="contest-a")
    assert result["kinds"] == {"数字冲突": 1, "表述": 1, "维度调整": 1}
    assert result["finding_total"] == 2
    assert result["reviews_with_changes"] == 1


def test_conflict_aggregation_skips_and_counts_unparsable_json(engine):
    from backend.app.chat.analytics import summarize_conflicts

    with Session(engine) as session:
        _save(session, "good", changes=[{"kind": "表述", "finding_kind": "wording", "target": "甲"}])
        _save(session, "broken", changes=[])
        session.execute(text("UPDATE review SET change_list=:value WHERE review_id='broken'"),
                        {"value": "{not-json"})
        session.commit()
        result = summarize_conflicts(session, contest_id="contest-a")
    assert result["unparsable"] == 1
    assert result["finding_total"] == 1
    assert result["kinds"] == {"表述": 1}


def test_conflict_hotspots_are_sorted_limited_and_cap_example_ids(engine):
    from backend.app.chat.analytics import summarize_conflicts

    with Session(engine) as session:
        for index in range(5):
            _save(session, f"same-{index}", changes=[{
                "kind": "数字冲突", "finding_kind": "conflict", "target": "热门指标",
            }])
        _save(session, "other", changes=[{
            "kind": "表述", "finding_kind": "wording", "target": "次要指标",
        }])
        result = summarize_conflicts(session, contest_id="contest-a", top=1)
    assert len(result["hotspots"]) == 1
    assert result["hotspots"][0]["target"] == "热门指标"
    assert result["hotspots"][0]["count"] == 5
    assert len(result["hotspots"][0]["review_ids"]) <= 3


def test_evidence_gaps_require_insufficient_band_and_empty_quote(engine):
    from backend.app.chat.analytics import evidence_gaps

    with Session(engine) as session:
        _save(session, "gap", dimensions=[_dim("不足", "   ")])
        _save(session, "supported", dimensions=[_dim("证据不足", "有原句")])
        result = evidence_gaps(session, contest_id="contest-a", dimension_code="assumption")
    assert result["count"] == 1
    assert result["gaps"] == [{
        "review_id": "gap", "dimension_code": "assumption", "band": "不足", "has_quote": False,
    }]


def test_analytics_route_permission_validation_and_required_contest(client, engine, actors):
    student = _headers(engine, actors["student"])
    teacher = _headers(engine, actors["teacher"])
    denied = client.post("/api/chat/analytics", headers=student,
                         json={"contest_id": "contest-a", "kind": "bands"})
    invalid_kind = client.post("/api/chat/analytics", headers=teacher,
                               json={"contest_id": "contest-a", "kind": "bogus"})
    missing_contest = client.post("/api/chat/analytics", headers=teacher, json={"kind": "bands"})
    assert [denied.status_code, invalid_kind.status_code, missing_contest.status_code] == [403, 400, 400]


def test_bands_route_matches_direct_aggregation_result(client, engine, actors):
    from backend.app.chat.analytics import compare_bands

    with Session(engine) as session:
        _save(session, "a1", dimensions=[_dim("充分")])
        session.commit()
        expected = compare_bands(session, contest_id="contest-a")
    response = client.post(
        "/api/chat/analytics", headers=_headers(engine, actors["teacher"]),
        json={"contest_id": "contest-a", "kind": "bands"},
    )
    assert response.status_code == 200
    assert response.json() == {"kind": "bands", "result": expected}


def test_summary_rejects_citations_outside_available_set(client, engine, actors, monkeypatch):
    hits = [_hit(f"{index:032x}") for index in range(3)]
    citations = [f"[review_id={item['review_id']} dim=assumption]" for item in hits]
    answer = " ".join(citations + ["[review_id=outside-a dim=assumption]", "[review_id=outside-b dim=method]"])
    _install_fakes(client, lambda *a, **k: hits, lambda messages: answer)
    response = client.post(
        "/api/chat/summary", headers=_headers(engine, actors["teacher"]),
        json={"contest_id": "contest-a"},
    )
    assert response.status_code == 200
    assert len(response.json()["refs"]) == 3
    assert response.json()["notes"]["rejected"] == 2
    assert "outside" not in response.json()["content"]


def test_summary_marks_short_evidence_and_appends_fixed_notice(client, engine, actors):
    hit = _hit("a" * 32)
    _install_fakes(client, lambda *a, **k: [hit],
                   lambda messages: f"摘要 [review_id={hit['review_id']} dim=assumption]")
    response = client.post(
        "/api/chat/summary", headers=_headers(engine, actors["teacher"]),
        json={"contest_id": "contest-a"},
    )
    assert response.status_code == 200
    assert response.json()["notes"]["evidence_short"] == 1
    assert response.json()["content"].endswith("（可用证据不足 3 条，已如实标注 1 条）")


def test_summary_persists_only_to_owned_session_when_requested(client, engine, actors):
    owner_headers = _headers(engine, actors["teacher"])
    other_headers = _headers(engine, actors["teacher2"])
    own_session = client.post("/api/chat/sessions", headers=owner_headers, json={}).json()["session_id"]
    other_session = client.post("/api/chat/sessions", headers=other_headers, json={}).json()["session_id"]
    hit = _hit("a" * 32)
    _install_fakes(client, lambda *a, **k: [hit],
                   lambda messages: f"摘要 [review_id={hit['review_id']} dim=assumption]")

    own = client.post("/api/chat/summary", headers=owner_headers,
                      json={"contest_id": "contest-a", "session_id": own_session})
    hidden = client.post("/api/chat/summary", headers=owner_headers,
                         json={"contest_id": "contest-a", "session_id": other_session})
    exported = client.post("/api/chat/summary", headers=owner_headers, json={"contest_id": "contest-a"})
    assert own.status_code == exported.status_code == 200
    assert hidden.status_code == 404
    with Session(engine) as session:
        own_messages = chat_store.load_messages(session, own_session)
        assert len(own_messages) == 1
        assert own_messages[0].role == "assistant"
        assert session.scalar(select(func.count()).select_from(chat_models.ChatMessage)) == 1
