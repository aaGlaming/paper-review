# 修改清单与评测测试。
# 不访问网络、不读真实 .env、不连生产库：评测是纯计算，评审记录落在 sqlite 内存库的事务里。
# 清单只转写上游已有的档位与审查结果，删掉上游记录后对应建议必须消失。

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.api.app import create_app  # noqa: E402
from backend.app.api.routes import get_session  # noqa: E402
from backend.app.report import change_list, evaluation, models, store  # noqa: E402
from backend.app.report.change_list import build_change_list, render_change_list  # noqa: E402
from backend.app.report.evaluation import run_eval, summarize_eval  # noqa: E402

AWARD_PATTERN = re.compile(r"一等奖|二等奖|三等奖|获奖概率|获奖|名次")
FORBIDDEN_SOURCE_TOKENS = (
    "httpx",
    "requests",
    "urllib",
    "aiohttp",
    "openai",
    "backend.app.llm",
    "cumcm-",
)

ENGINE = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
models.ReportBase.metadata.create_all(ENGINE)


@pytest.fixture()
def session():
    """内存库里的外层事务：进入时清空两张表，结束整体回滚。"""
    connection = ENGINE.connect()
    transaction = connection.begin()
    test_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        test_session.execute(delete(models.ReviewDimension))
        test_session.execute(delete(models.Review))
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


def _finding(kind: str, *, constraint_id: str | None = None, indicator: str = "", text_: str = ""):
    evidence = [{"char_start": 10, "char_end": 16, "text": text_}] if text_ else []
    return {
        "kind": kind,
        "constraint_id": constraint_id,
        "indicator": indicator,
        "evidence": evidence,
        "message": f"{kind}：{indicator or constraint_id}",
    }


def _findings() -> list[dict]:
    return [
        _finding("数字冲突", indicator="盘入终止时刻", text_="412 s"),
        _finding("引用缺失", indicator="引用 [12]", text_="[12]"),
        _finding("缺少情形", constraint_id="demo-case", indicator="50%降价"),
    ]


def _dimension_results() -> dict:
    return {
        "assumption": {"band": "充分", "status": "充分", "quote": "把手简化为孔中心点", "chunk_ids": ["c1"]},
        "modeling": {"band": "证据不足", "status": "证据不足", "quote": None, "chunk_ids": []},
        "solution": {"band": "基本", "status": "基本", "quote": "迭代步长 0.01 s", "chunk_ids": ["c2"]},
        "constraint_check": {"band": "引用失败", "status": "引用失败", "quote": "对不上的句子", "chunk_ids": ["c3"]},
        "presentation": {"band": "基本", "status": "基本", "quote": "表格缺少单位", "chunk_ids": ["c4"]},
    }


DIMENSIONS = [
    {"dimension_code": "assumption", "name": "假设的合理性", "weight": 20},
    {"dimension_code": "modeling", "name": "建模是否针对本题", "weight": 20},
    {"dimension_code": "solution", "name": "求解与结果", "weight": 20},
    {"dimension_code": "constraint_check", "name": "检验与题目约束", "weight": 20},
    {"dimension_code": "presentation", "name": "表述与结构", "weight": 20},
]


def _build(findings=None, dimension_results=None):
    return build_change_list(
        dimension_results if dimension_results is not None else _dimension_results(),
        findings if findings is not None else _findings(),
        DIMENSIONS,
    )


# --- 用例 1-5：清单的结构与上游可删 --------------------------------------------


def test_first_item_is_constraint_or_number_conflict():
    items = _build()

    assert items
    assert items[0]["kind"] in {"题目约束", "数字冲突"}


def test_insufficient_evidence_sits_between_constraints_and_wording():
    items = _build()

    kinds = [item["kind"] for item in items]
    assert "证据不足" in kinds and "表述" in kinds
    assert kinds.index("证据不足") > 0
    assert kinds.index("表述") > kinds.index("证据不足")
    assert kinds[-1] == "表述", "表述排在最后一段"
    sections = [item["section"] for item in items]
    assert sections == sorted(sections, key=lambda name: [
        change_list.SECTION_CONSTRAINTS,
        change_list.SECTION_INSUFFICIENT,
        change_list.SECTION_PRESENTATION,
    ].index(name))


def test_every_item_carries_an_upstream_id():
    items = _build()

    assert items
    assert [item for item in items if not item.get("upstream_id")] == []
    targets = {item["upstream_id"] for item in items}
    assert "dimension:modeling" in targets, "证据不足那条指向维度的 dimension_code"
    assert any(target.startswith("finding:") for target in targets), "审查类指向 finding 的 kind 与标识"


def test_removing_an_upstream_finding_drops_its_item():
    findings = _findings()
    before = _build(findings=findings)

    dropped = findings[0]
    dropped_id = f"finding:{dropped['kind']}:{dropped['indicator']}"
    after = _build(findings=findings[1:])

    assert any(item["upstream_id"] == dropped_id for item in before)
    assert not any(item["upstream_id"] == dropped_id for item in after)
    assert len(after) == len(before) - len(
        [item for item in before if item["upstream_id"] == dropped_id]
    )


def test_removing_a_dimension_drops_its_items():
    before = _build()
    results = _dimension_results()
    del results["presentation"]
    del results["modeling"]

    after = _build(dimension_results=results)

    affected = [
        item
        for item in before
        if item.get("dimension_code") in {"presentation", "modeling"}
    ]
    assert affected, before
    assert not any(
        item.get("dimension_code") in {"presentation", "modeling"} for item in after
    )
    assert len(after) == len(before) - len(affected)


# --- 用例 6：奖项字样 -----------------------------------------------------------


def test_report_text_and_api_json_have_no_award_words(client, session):
    items = _build()
    rendered = render_change_list(items)

    assert not AWARD_PATTERN.search(rendered), rendered
    assert change_list.contains_award_words(rendered) is False
    assert not AWARD_PATTERN.search(json.dumps(items, ensure_ascii=False))

    store.save_review(
        "review-award",
        contest_id="cumcm-2024-A",
        rubric_id="cumcm-2024-A-v1",
        rubric_version=1,
        model_name="unit-model",
        dimensions=_dimension_results(),
        session=session,
    )
    bodies = [
        client.get("/api/samples").json(),
        client.get("/api/samples", params={"is_demo": "true"}).json(),
        client.get("/api/eval/summary").json(),
        client.get("/api/reviews/review-award").json(),
    ]
    for body in bodies:
        assert not AWARD_PATTERN.search(json.dumps(body, ensure_ascii=False)), body


# --- 用例 7-8：三项指标的算法 ---------------------------------------------------


def test_band_agreement_rate_counts_matching_dimensions():
    gold = [
        {"dimension_code": code, "band": band}
        for code, band in zip(
            ("assumption", "modeling", "solution", "constraint_check", "presentation"),
            ("充分", "充分", "充分", "不足", "证据不足"),
            strict=True,
        )
    ]
    system = [
        {"dimension_code": code, "band": band, "quote": f"原句 {code}", "status": band}
        for code, band in (
            ("assumption", "充分"),
            ("modeling", "充分"),
            ("solution", "充分"),
            ("constraint_check", "基本"),
            ("presentation", "不足"),
        )
    ]
    pair = (gold, system, {item["dimension_code"]: True for item in system})

    outcome = summarize_eval([pair], corpus_papers=15)

    assert outcome["band_agreement"]["matched"] == 3
    assert outcome["band_agreement"]["total"] == 5
    assert outcome["band_agreement"]["rate"] == pytest.approx(0.6)

    empty = summarize_eval([], corpus_papers=15)

    assert empty["band_agreement"]["total"] == 0
    assert empty["band_agreement"]["rate"] is None
    assert "无可算样本" in empty["band_agreement"]["caliber"]
    assert empty["gradable_dimensions"] == 0


def test_insufficient_evidence_hit_counts_gold_insufficient():
    gold = [
        {"dimension_code": "assumption", "band": "证据不足"},
        {"dimension_code": "modeling", "band": "证据不足"},
    ]
    system = [
        {"dimension_code": "assumption", "band": "证据不足", "quote": None, "status": "证据不足"},
        {"dimension_code": "modeling", "band": "充分", "quote": "原句", "status": "充分"},
    ]
    pair = (gold, system, {"modeling": True})

    outcome = summarize_eval([pair])

    assert outcome["insufficient_evidence_hit"]["matched"] == 1
    assert outcome["insufficient_evidence_hit"]["total"] == 2
    assert outcome["insufficient_evidence_hit"]["rate"] == pytest.approx(0.5)
    assert outcome["quote_exact_match"]["total"] == 1, "只有给出原句的维度进分母"
    assert outcome["quote_exact_match"]["matched"] == 1


# --- 用例 9-10：评审记录持久化 --------------------------------------------------


def test_new_rubric_version_does_not_rewrite_old_reviews(session):
    old = store.save_review(
        "review-v1",
        contest_id="cumcm-2024-A",
        rubric_id="cumcm-2024-A-v1",
        rubric_version=1,
        model_name="unit-model",
        dimensions={"assumption": {"band": "基本", "status": "基本", "quote": "旧记录的原句", "chunk_ids": ["c-old"]}},
        session=session,
    )
    assert old["rubric_version"] == 1

    new = store.save_review(
        "review-v2",
        contest_id="cumcm-2024-A",
        rubric_id="cumcm-2024-A-v2",
        rubric_version=2,
        model_name="unit-model",
        dimensions={"assumption": {"band": "充分", "status": "充分", "quote": "新记录的原句", "chunk_ids": ["c-new"]}},
        session=session,
    )
    assert new["rubric_version"] == 2

    again = store.save_review(
        "review-v1",
        contest_id="cumcm-2024-A",
        rubric_id="cumcm-2024-A-v2",
        rubric_version=2,
        model_name="another-model",
        dimensions={"assumption": {"band": "充分", "status": "充分", "quote": "改写后的原句", "chunk_ids": ["c-new"]}},
        session=session,
    )
    assert again["rubric_version"] == 1, "旧记录的量规版本不因新发布而改变"
    assert again["rubric_id"] == "cumcm-2024-A-v1"
    assert again["model_name"] == "unit-model"

    reloaded = store.load_review("review-v1", session=session)
    assert reloaded["rubric_version"] == 1
    assert reloaded["dimensions"][0]["quote"] == "旧记录的原句"
    assert reloaded["dimensions"][0]["chunk_ids"] == ["c-old"]


def test_new_review_round_trips_change_list_and_old_review_is_explained(session):
    change_list = [{"section": "证据不足", "kind": "证据不足", "upstream_id": "dimension:assumption", "evidence": [], "action": "补充依据"}]
    saved = store.save_review(
        "review-with-change-list",
        contest_id="contest-a",
        dimensions=_dimension_results(),
        change_list=change_list,
        session=session,
    )
    loaded = store.load_review("review-with-change-list", session=session)

    assert saved["change_list"] == change_list
    assert loaded["change_list"] == change_list
    assert loaded.get("change_list_note") is None

    session.add(models.Review(review_id="review-old-without-list", change_list=None))
    session.flush()
    old = store.load_review("review-old-without-list", session=session)
    assert old["change_list"] == []
    assert old["change_list_note"] == "该记录为旧数据，未保存审查清单"


def test_report_schema_adds_nullable_change_list_column_to_existing_review_table():
    legacy_engine = create_engine("sqlite+pysqlite:///:memory:")
    with legacy_engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE review (review_id VARCHAR(64) PRIMARY KEY, contest_id VARCHAR(64) NOT NULL, "
            "rubric_id VARCHAR(64) NOT NULL, rubric_version INTEGER NOT NULL, model_name VARCHAR(128) NOT NULL, "
            "created_at DATETIME NOT NULL)"
        ))

    models.create_report_schema(legacy_engine)
    models.create_report_schema(legacy_engine)
    model_columns = {column["name"] for column in inspect(legacy_engine).get_columns("review")}
    with legacy_engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO review (review_id, contest_id, rubric_id, rubric_version, model_name, created_at) "
            "VALUES ('legacy', '', '', 1, '', CURRENT_TIMESTAMP)"
        ))
        stored_value = connection.execute(text("SELECT change_list FROM review WHERE review_id='legacy'")).scalar_one()

    assert "change_list" in model_columns
    assert stored_value is None
    legacy_engine.dispose()


def test_loading_old_review_keeps_contest_version_and_quotes(session, client):
    store.save_review(
        "review-old",
        contest_id="cumcm-2024-C",
        rubric_id="cumcm-2024-C-v1",
        rubric_version=1,
        model_name="unit-model",
        dimensions={
            "solution": {"band": "基本", "status": "基本", "quote": "方案对应的目标值为 974 万元", "chunk_ids": ["c-1"]},
            "constraint_check": {"band": "证据不足", "status": "证据不足", "quote": None, "chunk_ids": []},
        },
        session=session,
    )

    loaded = store.load_review("review-old", session=session)
    assert loaded["contest_id"] == "cumcm-2024-C"
    assert loaded["rubric_version"] == 1
    quotes = {item["dimension_code"]: item["quote"] for item in loaded["dimensions"]}
    assert quotes["solution"] == "方案对应的目标值为 974 万元"
    assert quotes["constraint_check"] is None

    response = client.get("/api/reviews/review-old")
    assert response.status_code == 200
    body = response.json()
    assert body["contest_id"] == "cumcm-2024-C"
    assert body["rubric_version"] == 1
    assert {item["quote"] for item in body["dimensions"]} >= {"方案对应的目标值为 974 万元", None}
    assert store.load_review("review-missing", session=session) is None
    assert client.get("/api/reviews/review-missing").status_code == 404


# --- 用例 11：源码约束 ---------------------------------------------------------


def test_report_sources_have_no_http_no_llm_and_no_contest_branch():
    paths = sorted((PROJECT_ROOT / "backend" / "app" / "report").glob("*.py"))
    assert paths
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_SOURCE_TOKENS:
            assert token not in source, f"{path}: {token}"
        assert "backend.app.retrieve" not in source, path
        assert "backend.app.llm" not in source, path


# --- 用例 12-13：接口与评测脚本 -------------------------------------------------


def test_new_endpoints_return_200(client):
    samples = client.get("/api/samples")
    assert samples.status_code == 200
    payload = samples.json()
    assert payload["samples"], payload
    assert any(item["is_demo"] for item in payload["samples"])
    assert any(not item["is_demo"] for item in payload["samples"])

    demos_only = client.get("/api/samples", params={"is_demo": "true"}).json()["samples"]
    assert demos_only and all(item["is_demo"] for item in demos_only)
    assert len(demos_only) == 3

    summary = client.get("/api/eval/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["corpus_papers"] == 15
    assert body["gradable_papers"] == 12
    assert body["gradable_dimensions"] == 60
    assert body["insufficient_evidence_hit"]["total"] == 2


def test_run_eval_reports_source_and_calibers():
    deterministic = run_eval()

    assert deterministic["source"] == "deterministic"
    assert deterministic["corpus_papers"] == 15
    assert deterministic["gradable_papers"] == 12
    assert deterministic["gradable_dimensions"] == 60
    assert deterministic["insufficient_evidence_hit"]["total"] == 2
    for key in ("band_agreement", "quote_exact_match", "insufficient_evidence_hit"):
        metric = deterministic[key]
        assert metric["caliber"], key
        assert metric["total"] > 0, key
        assert 0.0 <= metric["rate"] <= 1.0, key
    rendered = json.dumps(deterministic, ensure_ascii=False)
    assert not re.search(r"≥\s*0?\.\d|accuracy_target|target_accuracy", rendered)

    class FakeChat:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, messages, temperature=0.2, *, transport=None) -> str:
            self.calls += 1
            return json.dumps({"band": "证据不足", "chunk_id": "c1", "quote": "无"}, ensure_ascii=False)

    fake = FakeChat()
    modeled = run_eval(chat=fake)

    assert modeled["source"] == "model"
    assert fake.calls > 0
    assert modeled["insufficient_evidence_hit"]["matched"] == 2, "全判证据不足时两项 gold 都命中"
