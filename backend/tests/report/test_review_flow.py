# 评审创建、继续与读取的流程测试（v0.8.1）。
# 不访问网络、不读真实 .env、不连生产库：状态图用内存检查点，评审记录落在 sqlite 内存库的事务里。
# 量规从库里读：同一个内存库在建评审记录表之外，也建赛题那七张表并塞一条已发布量规，
# 用它当「库里的真值」——行数守卫拿它比对，不写死维度个数。

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.api.app import create_app  # noqa: E402
from backend.app.api.routes import get_graph, get_session  # noqa: E402
from backend.app.graph.review_graph import build_review_graph  # noqa: E402
from backend.app.importing import models as importing_models  # noqa: E402
from backend.app.importing.catalog import DIMENSION_CODES, DIMENSION_NAMES  # noqa: E402
from backend.app.report import models, rubric, store  # noqa: E402
from backend.app.review import samples as review_samples  # noqa: E402

AWARD_PATTERN = re.compile(r"一等奖|二等奖|三等奖|获奖概率|获奖|名次")
FORBIDDEN_TOKENS = (
    "cumcm-",
    "httpx",
    "requests",
    "urllib",
    "aiohttp",
    "openai",
    "backend.app.llm",
)

CONTEST_ID = "cumcm-2024-A"
RUBRIC_ID = "cumcm-2024-A-v1"

# 章节类型按维度收窄，全部能在下面这份稿子里命中；稿子里埋一处数字冲突供 change_list 取证。
SECTION_TYPES_BY_DIMENSION: dict[str, list[str]] = {
    "assumption": ["假设"],
    "modeling": ["模型"],
    "solution": ["求解"],
    "constraint_check": ["检验"],
    "presentation": ["摘要"],
}

PAPER = """# 摘要

本文求解盘入问题，求得盘入终止时刻为 412 s。

# 假设

把手简化为孔中心点，忽略板凳宽度。

# 模型建立

按等距螺线建立方程。

# 求解

迭代步长 0.01 s。

# 结果

盘入终止时刻为 386 s。

# 检验

验证把手速度不超过 2 m/s。

# 参考文献

[1] 某教材.
"""

ENGINE = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
models.ReportBase.metadata.create_all(ENGINE)
importing_models.Base.metadata.create_all(ENGINE)


def _seed_catalog() -> None:
    """往内存库里塞一道已发布赛题与它那一版已发布量规（库里的真值）。"""
    with Session(ENGINE) as work:
        work.add(
            importing_models.Contest(
                contest_id=CONTEST_ID,
                year=2024,
                problem_code="A",
                title="板凳龙",
                statement="题面正文",
                status="published",
            )
        )
        work.add(
            importing_models.Rubric(
                rubric_id=RUBRIC_ID,
                contest_id=CONTEST_ID,
                version=1,
                status="published",
                source_template_id=None,
            )
        )
        for code in DIMENSION_CODES:
            work.add(
                importing_models.Dimension(
                    dimension_id=f"{RUBRIC_ID}-{code}",
                    rubric_id=RUBRIC_ID,
                    code=code,
                    name=DIMENSION_NAMES[code],
                    weight=20,
                    evidence_prompts=["请给出依据"],
                    section_types=list(SECTION_TYPES_BY_DIMENSION[code]),
                    bands=[
                        {"band": "充分", "score": 90, "description": "充分"},
                        {"band": "基本", "score": 70, "description": "基本"},
                        {"band": "不足", "score": 40, "description": "不足"},
                        {"band": "证据不足", "score": None, "description": "证据不足"},
                    ],
                )
            )
        work.add(
            importing_models.Constraint(
                constraint_id="demo-mention",
                contest_id=CONTEST_ID,
                name="把手简化为孔中心点",
                check_type="mention",
                params={"keywords": ["孔中心点"]},
                section_types=["假设"],
            )
        )
        work.commit()


_seed_catalog()


# --- 夹具 -----------------------------------------------------------------------


@pytest.fixture()
def session():
    """内存库里的外层事务：进入时清空评审三张表，结束整体回滚。"""
    connection = ENGINE.connect()
    transaction = connection.begin()
    test_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        test_session.execute(delete(models.ReviewDimension))
        test_session.execute(delete(models.Review))
        test_session.execute(delete(models.ReviewSession))
        test_session.flush()
        yield test_session
    finally:
        test_session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def app(session):
    application = create_app()
    application.dependency_overrides[get_session] = lambda: session
    yield application


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- 小工具 ---------------------------------------------------------------------


def _keys(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def _count(session: Session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _create(client, **payload) -> dict[str, Any]:
    body = {"contest_id": CONTEST_ID, **payload}
    response = client.post("/api/reviews", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _resume(client, review_id: str, sections) -> dict[str, Any]:
    response = client.post(f"/api/reviews/{review_id}/resume", json={"sections": sections})
    assert response.status_code == 200, response.text
    return response.json()


def _graph_state(graph, review_id: str) -> dict[str, Any]:
    return dict(graph.get_state({"configurable": {"thread_id": review_id}}).values or {})


# --- 1-4：创建 ------------------------------------------------------------------


def test_create_review_stops_at_confirm_and_returns_no_band(client):
    body = _create(client, paper_text=PAPER)

    assert body["status"] == "待确认"
    assert body["sections"], body
    raw = json.dumps(body, ensure_ascii=False)
    assert '"band"' not in raw, "未确认不评分，响应里不得出现档位字段"
    assert "band" not in set(_keys(body)), body


def test_create_review_reads_the_demo_file_when_given_sample_id(client, session):
    body = _create(client, sample_id="bench-dragon")

    stored = store.load_session(body["review_id"], session=session)
    assert stored is not None
    assert stored["paper_text"] == review_samples.load_demo_text("bench-dragon.md")
    assert stored["sections"], "按演示稿正文切出了章节树"


@pytest.mark.parametrize("blank", ["", "   ", "\n\t  \n"])
def test_blank_paper_text_is_rejected_without_creating_a_session(client, session, blank):
    response = client.post("/api/reviews", json={"paper_text": blank, "contest_id": CONTEST_ID})

    assert response.status_code == 400, response.text
    assert _count(session, models.ReviewSession) == 0, "拒单时不得产生 review_id"


def test_create_review_rejects_both_or_neither_source(client, session):
    both = client.post(
        "/api/reviews",
        json={"paper_text": PAPER, "sample_id": "bench-dragon", "contest_id": CONTEST_ID},
    )
    neither = client.post("/api/reviews", json={"contest_id": CONTEST_ID})

    assert both.status_code == 400, both.text
    assert neither.status_code == 400, neither.text
    assert _count(session, models.ReviewSession) == 0


# --- 5-9：继续与落库 -------------------------------------------------------------


def test_resume_finishes_and_saves_review_rows(client, session):
    created = _create(client, paper_text=PAPER)
    body = _resume(client, created["review_id"], created["sections"])

    assert body["status"] == "完成"
    assert _count(session, models.Review) == 1
    truth = rubric.load_review_inputs(CONTEST_ID, session=session)["dimensions"]
    assert truth, "内存库里那条已发布量规是行数的真值"
    assert _count(session, models.ReviewDimension) == len(truth)


def test_resume_reports_deterministic_source_without_award_words(client):
    created = _create(client, paper_text=PAPER)
    body = _resume(client, created["review_id"], created["sections"])

    assert body["source"] == "deterministic"
    assert body["model_name"] == "deterministic"
    raw = json.dumps(body, ensure_ascii=False)
    assert not AWARD_PATTERN.search(raw), raw
    assert body["contest_id"] == CONTEST_ID
    assert body["rubric_id"] == RUBRIC_ID
    assert body["rubric_version"] == 1


def test_resume_uses_model_graph_when_four_required_settings_are_present(client, monkeypatch):
    from backend.app.api import routes as route_module
    from backend.app.llm import client as llm_client

    for key, value in {
        "LLM_BASE_URL": "https://chat.example/v1",
        "LLM_API_KEY": "test-chat-key",
        "LLM_MODEL": "test-chat-model",
        "EMBEDDING_MODEL": "test-embedding-model",
    }.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setattr(
        route_module,
        "_prepare_review_index",
        lambda **_kwargs: {
            "parents": [],
            "vector_enabled": False,
            "retriever": lambda _request: {
                "status": "命中",
                "rounds": 1,
                "parents": [{
                    "parent_id": "paper-parent",
                    "section_type": "模型",
                    "content": "本文采用结构化建模方法。",
                    "chunk_ids": ["paper-parent-00"],
                }],
                "queries": ["模型依据"],
            },
        },
    )
    monkeypatch.setattr(
        llm_client,
        "chat",
        lambda *_args, **_kwargs: json.dumps({
            "band": "不足", "chunk_id": "paper-parent-00", "quote": "本文采用结构化建模"
        }, ensure_ascii=False),
    )

    created = _create(client, paper_text=PAPER)
    body = _resume(client, created["review_id"], created["sections"])

    assert body["source"] == "model"
    assert body["model_name"] == "test-chat-model"
    assert body["dimensions"]
    assert all(item["band"] == "不足" for item in body["dimensions"])
    assert all(item["chat_calls"] == 1 for item in body["dimensions"])


def test_dimension_rows_match_the_rubric_in_the_database(client, session):
    created = _create(client, paper_text=PAPER)
    _resume(client, created["review_id"], created["sections"])

    truth = rubric.load_review_inputs(CONTEST_ID, session=session)["dimensions"]
    rows = list(session.scalars(select(models.ReviewDimension)))
    assert {row.dimension_code for row in rows} == {item["dimension_code"] for item in truth}
    assert len(rows) == len(truth), "行数按库里量规的真值，不写死"


def test_resume_survives_a_process_restart(app, client):
    created = _create(client, paper_text=PAPER)
    fresh_graph = build_review_graph()  # 全新 InMemorySaver：等价于进程重启
    app.dependency_overrides[get_graph] = lambda: fresh_graph

    body = _resume(client, created["review_id"], created["sections"])

    assert body["status"] == "完成"
    assert body["dimensions"], "重启后仍要按库里的量规出各维档位"
    final = _graph_state(fresh_graph, created["review_id"])
    assert final["parse_node_calls"] == 1, "还原后没有重新解析章节树"
    assert final["score_node_calls"] == 1


def test_resume_is_idempotent(app, client, session):
    created = _create(client, paper_text=PAPER)
    graph = build_review_graph()
    app.dependency_overrides[get_graph] = lambda: graph

    first = _resume(client, created["review_id"], created["sections"])
    second = _resume(client, created["review_id"], created["sections"])

    assert first["status"] == second["status"] == "完成"
    first_quotes = {item["dimension_code"]: item["quote"] for item in first["dimensions"]}
    second_quotes = {item["dimension_code"]: item["quote"] for item in second["dimensions"]}
    assert first_quotes == second_quotes
    assert _count(session, models.Review) == 1
    assert _graph_state(graph, created["review_id"])["score_node_calls"] == 1, "二次继续不重复评分"


# --- 10-11：读取的两段式与 404 ---------------------------------------------------


def test_get_review_returns_sections_then_report(client):
    created = _create(client, paper_text=PAPER)
    review_id = created["review_id"]

    pending = client.get(f"/api/reviews/{review_id}")
    assert pending.status_code == 200
    assert pending.json()["status"] == "待确认"
    assert pending.json()["sections"]
    assert pending.json()["confirmed"] is False

    _resume(client, review_id, created["sections"])
    done = client.get(f"/api/reviews/{review_id}")
    assert done.status_code == 200
    body = done.json()
    assert body["contest_id"] == CONTEST_ID
    assert body["rubric_version"] == 1
    assert body["dimensions"]


def test_unknown_review_id_returns_404(client):
    assert client.post("/api/reviews/nope/resume", json={"sections": []}).status_code == 404
    assert client.get("/api/reviews/nope").status_code == 404


# --- 12：change_list 的字符偏移 --------------------------------------------------


def test_change_list_evidence_points_back_into_the_paper(client):
    created = _create(client, paper_text=PAPER)
    body = _resume(client, created["review_id"], created["sections"])

    review_items = [
        item
        for item in body["change_list"]
        if item["kind"] in {"数字冲突", "题目约束"} and item["evidence"]
    ]
    assert review_items, body["change_list"]

    located = 0
    for item in review_items:
        for entry in item["evidence"]:
            assert entry["char_start"] < entry["char_end"]
            assert PAPER[entry["char_start"] : entry["char_end"]] == entry["text"]
            located += 1
    assert located > 0


# --- 13-14：源码约束与依赖可覆盖 -------------------------------------------------


def test_api_and_report_sources_stay_clean():
    for name in ("api", "report"):
        directory = PROJECT_ROOT / "backend" / "app" / name
        paths = sorted(directory.glob("*.py"))
        assert paths, name
        for path in paths:
            source = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_TOKENS:
                assert token not in source, f"{path}: {token}"
            if name == "report":
                assert "backend.app.retrieve" not in source, path


def test_session_and_graph_dependencies_can_be_overridden(app, client, session):
    fresh_graph = build_review_graph()
    app.dependency_overrides[get_graph] = lambda: fresh_graph

    created = _create(client, paper_text=PAPER)
    assert _graph_state(fresh_graph, created["review_id"]), "请求用的确实是被覆盖的图"

    store.save_review("probe-session", contest_id=CONTEST_ID, dimensions={}, session=session)
    assert client.get("/api/reviews/probe-session").status_code == 200, "接口走的是被覆盖的会话"


# --- 15：未绑定赛题不猜、不兜底 ---------------------------------------------------


def test_unbound_contest_yields_empty_dimensions_and_no_change_list(client, session):
    created = _create(client, paper_text=PAPER, contest_id=None)
    body = _resume(client, created["review_id"], created["sections"])

    assert body["status"] == "完成"
    assert body["rubric_id"] is None
    assert body["rubric_version"] is None
    assert body["dimensions"] == []
    assert body["change_list"] == []
    assert "未绑定赛题" in body["note"]
    assert _count(session, models.ReviewDimension) == 0
