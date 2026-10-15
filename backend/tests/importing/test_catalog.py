# 赛题包导入测试。
# 默认连真实 MySQL（连接串只从环境变量 MYSQL_DSN 读，凭据不写进本文件），
# 连不上才退到 sqlite 内存库跑同一套 ORM 与校验逻辑，并把实际环境写进 progress.md。
# 每个用例跑在外层事务里，结束整体回滚，用例之间互不残留。

from __future__ import annotations

import ast
import json
import re
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.api.app import create_app  # noqa: E402
from backend.app.api.routes import get_session  # noqa: E402
from backend.app.importing import catalog, db, models  # noqa: E402

CONTESTS_DIR = PROJECT_ROOT / "data" / "contests"
THREE_CONTESTS = ("cumcm-2024-A", "cumcm-2024-C", "cumcm-2025-A")
FIXTURE_CONTEST = "fixture-extra"
ALLOWED_CHECK_TYPES = {"mention", "numeric_range", "required_case"}

CONTEST_ID_PATTERN = re.compile(r"^(cumcm-\d{4}-[A-Za-z]+|fixture-[a-z]+)$")


def _probe_mysql(dsn: str | None) -> bool:
    if not dsn:
        return False
    try:
        engine = create_engine(dsn, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


try:
    _DSN = db.get_dsn()
except Exception:
    _DSN = None

MYSQL_REACHABLE = _probe_mysql(_DSN)


def _resolve_engine():
    if MYSQL_REACHABLE:
        return create_engine(_DSN, pool_pre_ping=True), "mysql"
    return (
        create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        ),
        "sqlite",
    )


ENGINE, BACKEND = _resolve_engine()
models.Base.metadata.create_all(ENGINE)


@pytest.fixture()
def session():
    """外层事务 + 保存点：用例内清空目录再跑，结束整体回滚，不改动库里的既有数据。"""
    connection = ENGINE.connect()
    transaction = connection.begin()
    test_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        for model in (
            models.Constraint,
            models.Dimension,
            models.Pitfall,
            models.Exemplar,
            models.Rubric,
            models.RubricTemplate,
            models.Contest,
        ):
            test_session.execute(delete(model))
        test_session.flush()
        yield test_session
    finally:
        test_session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _import(client: TestClient, package_dir: Path):
    return client.post("/api/imports", json={"package_dir": str(package_dir)})


def _publish(client: TestClient, contest_id: str):
    return client.post(f"/api/contests/{contest_id}/publish")


def _archive(client: TestClient, contest_id: str):
    return client.post(f"/api/contests/{contest_id}/archive")


def _contests(client: TestClient, **params) -> dict:
    response = client.get("/api/contests", params=params or None)
    assert response.status_code == 200, response.text
    return {item["contest_id"]: item for item in response.json()["contests"]}


def _published_count(session: Session, contest_id: str | None = None) -> int:
    statement = select(func.count()).select_from(models.Contest).where(
        models.Contest.status == "published"
    )
    if contest_id:
        statement = statement.where(models.Contest.contest_id == contest_id)
    return session.execute(statement).scalar_one()


def _published_rubric_count(session: Session, contest_id: str) -> int:
    return session.execute(
        select(func.count())
        .select_from(models.Rubric)
        .where(models.Rubric.contest_id == contest_id, models.Rubric.status == "published")
    ).scalar_one()


def _mutated_package(tmp_path: Path, contest_id: str, mutate) -> Path:
    target = tmp_path / contest_id
    shutil.copytree(CONTESTS_DIR / contest_id, target)
    mutate(target)
    return target


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _import_and_publish(client: TestClient, contest_id: str):
    response = _import(client, CONTESTS_DIR / contest_id)
    assert response.status_code == 200, response.text
    published = _publish(client, contest_id)
    assert published.status_code == 200, published.text
    return response.json()


# --- 用例 1 -------------------------------------------------------------------


def test_import_and_publish_makes_contest_readable(client):
    payload = _import_and_publish(client, "cumcm-2024-A")

    assert payload["contest_id"] == "cumcm-2024-A"
    item = _contests(client)["cumcm-2024-A"]
    assert item["status"] == "published"
    assert item["year"] == 2024
    assert item["problem_code"] == "A"
    assert item["rubric"]["version"] == 1
    assert item["rubric"]["status"] == "published"

    constraints = item["constraints"]
    assert constraints, "已发布赛题至少要能读到一条硬性条件"
    pitch = [one for one in constraints if one["check_type"] == "numeric_range" and "1.7" in one["name"]]
    assert pitch, constraints
    assert pitch[0]["params"] == {"min": 1.7, "max": 1.7, "unit": "m"}


# --- 用例 2 -------------------------------------------------------------------


def test_three_contests_import_with_expected_constraints(client):
    expected = {
        "cumcm-2024-A": {
            "板凳之间不能相撞": ("mention", {"keywords": ["碰撞", "相撞", "板凳宽度"]}),
            "盘入螺距为 1.7 m": ("numeric_range", {"min": 1.7, "max": 1.7, "unit": "m"}),
            "调头圆弧两段相切且半径 2 倍": ("mention", {"keywords": ["相切", "2 倍", "半径"]}),
            "龙头速度为 1 m/s": ("numeric_range", {"min": 1, "max": 1, "unit": "m/s"}),
            "把手速度不超过 2 m/s": ("numeric_range", {"min": 0, "max": 2, "unit": "m/s"}),
        },
        "cumcm-2024-C": {
            "同一地块不能连续重茬": ("mention", {"keywords": ["重茬", "连作", "连续种植"]}),
            "每块地三年内至少种植一次豆类": ("mention", {"keywords": ["豆类", "三年内至少一次"]}),
            "超额产量滞销情形": ("required_case", {"label": "滞销", "artifact": "result1_1"}),
            "超额产量按 50% 降价出售情形": (
                "required_case",
                {"label": "50%降价", "artifact": "result1_2"},
            ),
        },
        "cumcm-2025-A": {
            "烟幕云团以 3 m/s 下沉": ("numeric_range", {"min": 3, "max": 3, "unit": "m/s"}),
            "云团中心 10 m 范围内、起爆后 20 s 内可有效遮蔽": (
                "mention",
                {"keywords": ["10 m", "20 s"]},
            ),
            "无人机速度范围为 70～140 m/s": (
                "numeric_range",
                {"min": 70, "max": 140, "unit": "m/s"},
            ),
        },
    }

    for contest_id in THREE_CONTESTS:
        _import_and_publish(client, contest_id)

    listed = _contests(client)
    for contest_id, wanted in expected.items():
        item = listed[contest_id]
        got = {one["name"]: (one["check_type"], one["params"]) for one in item["constraints"]}
        assert got == wanted, contest_id
        for name, (check_type, _params) in wanted.items():
            assert check_type in ALLOWED_CHECK_TYPES
        joined = " ".join(wanted)
        assert re.search(r"\d", joined)


# --- 用例 3-6：坏包矩阵 --------------------------------------------------------


def test_weight_sum_must_be_100(client, tmp_path):
    def mutate(package: Path) -> None:
        payload = _load(package / "rubric.json")
        payload["dimensions"][0]["weight"] = 15
        _dump(package / "rubric.json", payload)

    response = _import(client, _mutated_package(tmp_path, "cumcm-2024-A", mutate))

    assert response.status_code == 400, response.text
    body = response.json()
    assert body["filename"] == "rubric.json"
    assert "weight" in body["field"]


def test_missing_required_field_is_rejected(client, tmp_path):
    def mutate(package: Path) -> None:
        payload = _load(package / "contest.json")
        del payload["title"]
        _dump(package / "contest.json", payload)

    response = _import(client, _mutated_package(tmp_path, "cumcm-2024-A", mutate))

    assert response.status_code == 400, response.text
    body = response.json()
    assert body["filename"] == "contest.json"
    assert body["field"] == "title"


def test_unregistered_check_type_is_rejected(client, tmp_path):
    def mutate(package: Path) -> None:
        payload = _load(package / "constraints.json")
        payload["constraints"][1]["check_type"] = "regex"
        _dump(package / "constraints.json", payload)

    response = _import(client, _mutated_package(tmp_path, "cumcm-2024-A", mutate))

    assert response.status_code == 400, response.text
    body = response.json()
    assert body["filename"] == "constraints.json"
    assert "check_type" in body["field"]


@pytest.mark.parametrize("mutation", ["missing_band", "scored_insufficient"])
def test_band_matrix_is_rejected(client, tmp_path, mutation):
    def mutate(package: Path) -> None:
        payload = _load(package / "rubric.json")
        bands = payload["dimensions"][0]["bands"]
        if mutation == "missing_band":
            payload["dimensions"][0]["bands"] = [
                band for band in bands if band["band"] != "证据不足"
            ]
        else:
            for band in bands:
                if band["band"] == "证据不足":
                    band["score"] = 0
        _dump(package / "rubric.json", payload)

    response = _import(client, _mutated_package(tmp_path, "cumcm-2024-A", mutate))

    assert response.status_code == 400, response.text
    body = response.json()
    assert body["filename"] == "rubric.json"
    assert "bands" in body["field"]


# --- 用例 7 -------------------------------------------------------------------


def test_failed_import_keeps_published_rows_unchanged(client, session, tmp_path):
    for contest_id in THREE_CONTESTS:
        _import_and_publish(client, contest_id)

    before_rows = _published_count(session)
    before_list = sorted(_contests(client))

    def mutate(package: Path) -> None:
        payload = _load(package / "rubric.json")
        payload["dimensions"][1]["bands"] = []
        _dump(package / "rubric.json", payload)

    response = _import(client, _mutated_package(tmp_path, "cumcm-2025-A", mutate))

    assert response.status_code == 400, response.text
    assert _published_count(session) == before_rows
    assert sorted(_contests(client)) == before_list
    assert _published_count(session, "cumcm-2025-A") == 1


# --- 用例 8 -------------------------------------------------------------------


def test_archived_contest_disappears_from_list(client, session):
    _import_and_publish(client, "cumcm-2024-C")
    assert "cumcm-2024-C" in _contests(client)

    response = _archive(client, "cumcm-2024-C")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "archived"
    assert "cumcm-2024-C" not in _contests(client)
    assert "cumcm-2024-C" in _contests(client, include_archived=True)
    row = session.get(models.Contest, "cumcm-2024-C")
    assert row.status == "archived"


def test_draft_contest_is_not_listed_before_publish(client):
    response = _import(client, CONTESTS_DIR / "cumcm-2024-A")

    assert response.status_code == 200, response.text
    assert "cumcm-2024-A" not in _contests(client)
    assert "cumcm-2024-A" in _contests(client, include_drafts=True)


# --- 用例 9 -------------------------------------------------------------------


def test_fixture_extra_uses_the_same_import_path(client):
    payload = _import_and_publish(client, FIXTURE_CONTEST)

    assert payload["contest_id"] == FIXTURE_CONTEST
    item = _contests(client)[FIXTURE_CONTEST]
    assert item["constraints"]
    assert {one["check_type"] for one in item["constraints"]} <= ALLOWED_CHECK_TYPES


def test_importing_and_api_sources_have_no_contest_id_branching():
    paths = sorted((PROJECT_ROOT / "backend" / "app" / "importing").glob("*.py"))
    paths += sorted((PROJECT_ROOT / "backend" / "app" / "api").glob("*.py"))
    assert paths, "没有找到导入层源码"

    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not CONTEST_ID_PATTERN.match(node.value.strip()), f"{path}: {node.value}"
            if isinstance(node, ast.Compare):
                for side in [node.left, *node.comparators]:
                    if isinstance(side, ast.Constant) and isinstance(side.value, str):
                        assert not CONTEST_ID_PATTERN.match(side.value.strip()), path
        assert "cumcm" not in source, path
        assert FIXTURE_CONTEST not in source, path


# --- 用例 10 ------------------------------------------------------------------


def test_copy_rubric_as_draft_bumps_version_and_keeps_single_published(client, session):
    _import_and_publish(client, "cumcm-2024-A")
    assert _published_rubric_count(session, "cumcm-2024-A") == 1

    copied = client.post("/api/contests/cumcm-2024-A/rubrics")

    assert copied.status_code == 200, copied.text
    draft = copied.json()
    assert draft["version"] == 2
    assert draft["status"] == "draft"
    assert _published_rubric_count(session, "cumcm-2024-A") == 1

    published = client.post(f"/api/rubrics/{draft['rubric_id']}/publish")

    assert published.status_code == 200, published.text
    assert published.json()["version"] == 2
    assert published.json()["status"] == "published"
    assert _published_rubric_count(session, "cumcm-2024-A") == 1
    item = _contests(client)["cumcm-2024-A"]
    assert item["rubric"]["version"] == 2


# --- 环境披露 -----------------------------------------------------------------


def test_backend_selection_follows_availability():
    assert BACKEND in {"mysql", "sqlite"}
    if MYSQL_REACHABLE:
        assert BACKEND == "mysql", "MYSQL_DSN 可连时必须连真实 MySQL"
    else:
        assert BACKEND == "sqlite", "连不上真实 MySQL 才退到 sqlite 内存库"
