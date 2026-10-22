from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.app import create_app
from backend.app.api.routes import get_session
from backend.app.auth.deps import current_user
from backend.app.auth.permissions import DEFAULT_PERMISSIONS
from backend.app.report import models


@pytest.fixture()
def dashboard_client(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.ReportBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scope():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def override_session():
        with scope() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    role = {"name": "teacher"}

    def override_user():
        name = role["name"]
        return {
            "user_id": f"{name}-id",
            "role": name,
            "permissions": list(DEFAULT_PERMISSIONS[name]),
        }

    app.dependency_overrides[current_user] = override_user
    with TestClient(app) as client:
        yield client, engine, role
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture(autouse=True)
def clear_dashboard_cache():
    from backend.app.report import dashboard

    dashboard.clear_cache()
    yield
    dashboard.clear_cache()


def test_student_is_forbidden_and_teacher_can_read_summary(dashboard_client):
    client, _, role = dashboard_client
    role["name"] = "student"
    assert client.get("/api/dashboard/summary").status_code == 403
    role["name"] = "teacher"
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200


def test_empty_database_returns_empty_arrays_and_null_gold(dashboard_client, monkeypatch):
    from backend.app.report import dashboard

    client, _, _ = dashboard_client
    monkeypatch.setattr(dashboard, "_gold_agreement", lambda: None)
    summary = client.get("/api/dashboard/summary").json()
    trend = client.get("/api/dashboard/trend?days=3").json()
    assert summary["contests"] == []
    assert summary["bands"] == []
    assert summary["conflicts"] == []
    assert summary["gold"] is None
    assert trend["days"] == 3
    assert len(trend["series"]) == 3
    assert all(row["total"] == row["ownerless"] == 0 for row in trend["series"])


def test_band_counts_keep_all_four_raw_keys_and_sum_to_dimension_rows(dashboard_client):
    client, engine, _ = dashboard_client
    with Session(engine) as session:
        for index, band in enumerate(("充分", "基本", "不足", "证据不足")):
            review_id = f"r{index}"
            session.add(models.Review(
                review_id=review_id, user_id=None, contest_id="contest-probe", rubric_id="r",
                rubric_version=1, model_name="m", created_at=models.utc_now(), change_list=[],
            ))
            session.add(models.ReviewDimension(review_id=review_id, dimension_code="d1", band=band,
                                               chunk_ids=[], quote=None, status=None))
        session.commit()
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    contest = next(item for item in body["contests"] if item["contest_id"] == "contest-probe")
    assert contest["review_count"] == 4
    d1 = next(item for item in body["bands"] if item["dimension_code"] == "d1")
    assert d1["counts"] == {"充分": 1, "基本": 1, "不足": 1, "证据不足": 1}
    assert sum(d1["counts"].values()) == 4


def test_insufficient_total_is_normalized_sum_of_two_raw_bands(dashboard_client):
    client, engine, _ = dashboard_client
    with Session(engine) as session:
        for index, band in enumerate(("不足", "证据不足", "基本")):
            review_id = f"r{index}"
            session.add(models.Review(
                review_id=review_id, user_id="u1", contest_id="c", rubric_id="r",
                rubric_version=1, model_name="m", created_at=models.utc_now(), change_list=[],
            ))
            session.add(models.ReviewDimension(review_id=review_id, dimension_code="d1", band=band,
                                               chunk_ids=[], quote=None, status=None))
        session.commit()
    body = client.get("/api/dashboard/summary").json()
    d1 = next(item for item in body["bands"] if item["dimension_code"] == "d1")
    assert d1["insufficient_total"] == d1["counts"]["不足"] + d1["counts"]["证据不足"] == 2


def test_cache_second_call_is_marked_and_equal_without_sleep(dashboard_client, monkeypatch):
    from backend.app.report import dashboard

    client, _, _ = dashboard_client
    clock = iter((100.0, 101.0))
    monkeypatch.setattr(dashboard, "_clock", lambda: next(clock))
    dashboard.clear_cache()
    first = client.get("/api/dashboard/summary").json()
    second = client.get("/api/dashboard/summary").json()
    assert first["cached"] is False
    assert second["cached"] is True
    assert {key: value for key, value in first.items() if key != "cached"} == {
        key: value for key, value in second.items() if key != "cached"
    }


def test_trend_uses_utc_day_and_keeps_ownerless_out_of_total(dashboard_client):
    client, engine, _ = dashboard_client
    with Session(engine) as session:
        session.add_all([
            models.Review(
                review_id="orphan", user_id=None, contest_id="c", rubric_id="r",
                rubric_version=1, model_name="m", created_at=models.utc_now(), change_list=[],
            ),
            models.Review(
                review_id="owned", user_id="u1", contest_id="c", rubric_id="r",
                rubric_version=1, model_name="m", created_at=models.utc_now(), change_list=[],
            ),
        ])
        session.commit()
    row = client.get("/api/dashboard/trend?days=1").json()["series"][0]
    assert row["total"] == 2
    assert row["ownerless"] == 1


def test_parse_only_reviews_are_not_submissions_and_are_counted_separately(dashboard_client):
    client, engine, _ = dashboard_client
    with Session(engine) as session:
        session.add_all([
            models.Review(
                review_id="parse-only", user_id="u1", contest_id="", rubric_id="",
                rubric_version=1, model_name="", created_at=models.utc_now(), change_list=[],
            ),
            *[
                models.Review(
                    review_id=f"scored-{index}", user_id="u1", contest_id="contest-a", rubric_id="rubric-a",
                    rubric_version=1, model_name="m", created_at=models.utc_now(), change_list=[],
                )
                for index in range(2)
            ],
        ])
        session.commit()

    summary = client.get("/api/dashboard/summary").json()

    assert summary["cards"]["total_submissions"] == 2
    assert summary["cards"]["parse_only"] == 1
    assert summary["cards"]["weekly_new"] == 2


def test_contest_distribution_excludes_parse_only_rows(dashboard_client):
    client, engine, _ = dashboard_client
    with Session(engine) as session:
        session.add_all([
            models.Review(
                review_id="parse-only", user_id="u1", contest_id="", rubric_id="",
                rubric_version=1, model_name="", created_at=models.utc_now(), change_list=[],
            ),
            *[
                models.Review(
                    review_id=f"scored-{index}", user_id="u1", contest_id="contest-a", rubric_id="rubric-a",
                    rubric_version=1, model_name="m", created_at=models.utc_now(), change_list=[],
                )
                for index in range(2)
            ],
        ])
        session.commit()

    contests = client.get("/api/dashboard/summary").json()["contests"]

    assert contests == [{"contest_id": "contest-a", "review_count": 2}]


def test_trend_excludes_parse_only_reviews(dashboard_client):
    client, engine, _ = dashboard_client
    with Session(engine) as session:
        session.add_all([
            models.Review(
                review_id="parse-only", user_id="u1", contest_id="", rubric_id="",
                rubric_version=1, model_name="", created_at=models.utc_now(), change_list=[],
            ),
            *[
                models.Review(
                    review_id=f"scored-{index}", user_id=None if index == 0 else "u1", contest_id="contest-a",
                    rubric_id="rubric-a", rubric_version=1, model_name="m", created_at=models.utc_now(),
                    change_list=[],
                )
                for index in range(2)
            ],
        ])
        session.commit()

    row = client.get("/api/dashboard/trend?days=1").json()["series"][0]

    assert row["total"] == 2
    assert row["ownerless"] == 1

