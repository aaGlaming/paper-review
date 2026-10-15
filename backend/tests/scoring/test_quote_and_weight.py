# 原句与加权测试。
# 一律注入假 chat，不访问网络、不读真实 .env；密钥为空也能跑完。
# 图侧的行为断言也写在本文件里（本版不新建 tests/graph 下的文件）。

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.graph import review_graph  # noqa: E402
from backend.app.graph.review_graph import (  # noqa: E402
    REVIEW_STATUSES,
    build_review_graph,
    create_review,
    resume_review,
)
from backend.app.importing.catalog import DIMENSION_CODES, DIMENSION_NAMES  # noqa: E402
from backend.app.retrieve.three_route import MAX_PARENTS  # noqa: E402
from backend.app.scoring import aggregate, selection  # noqa: E402
from backend.app.scoring.aggregate import weighted_sum  # noqa: E402

BAND_SUFFICIENT = "充分"
BAND_BASIC = "基本"
BAND_WEAK = "不足"
BAND_INSUFFICIENT = "证据不足"
STATUS_CITATION_FAILURE = "引用失败"
STATUS_FAILURE = "失败"

PAPER_TEXT = "\n".join(
    [
        "# 板凳龙运动分析",
        "",
        "## 一、模型假设",
        "板凳宽度不可忽略，把手简化为孔中心点。",
        "",
        "## 二、模型的建立",
        "按螺距 1.7 m 写出螺线参数方程。",
        "",
        "## 三、模型求解",
        "用迭代法逐段求解。",
        "",
        "## 四、结果分析",
        "结果按问题顺序给出。",
        "",
        "## 五、模型检验",
        "把手速度不超过 2 m/s。",
        "",
        "## 参考文献",
        "[1] 自建样例。",
    ]
)

# 固定切片：每维一段父块，下面的 quote 都取自这里。
EVIDENCE = {
    "assumption": "假设：板凳宽度不可忽略，把手简化为孔中心点。",
    "modeling": "模型：按螺距 1.7 m 写出螺线参数方程，调头由两段相切圆弧组成。",
    "solution": "求解：用迭代法逐段求解，龙头速度保持 1 m/s。",
    "constraint_check": "检验：把手速度不超过 2 m/s，逐条对照题目条件。",
    "presentation": "结果按问题顺序给出，表格标注了单位。",
}
QUOTES = {
    "assumption": "把手简化为孔中心点",
    "modeling": "调头由两段相切圆弧组成",
    "solution": "龙头速度保持 1 m/s",
    "constraint_check": "把手速度不超过 2 m/s",
    "presentation": "表格标注了单位",
}
DIMENSION_SECTION_TYPES = {
    "assumption": ["假设", "模型"],
    "modeling": ["模型", "求解"],
    "solution": ["求解", "结果"],
    "constraint_check": ["检验", "结果"],
    "presentation": ["结果", "参考文献"],
}

# 烟幕题里的固定切片：云团被写成静止，没有下沉，也没有 10 m / 20 s 的有效范围。
STATIC_SMOKE_EVIDENCE = "假设：烟幕云团在空间中静止不动，遮蔽效果只取决于投放位置。"
STATIC_SMOKE_QUOTE = "烟幕云团在空间中静止不动"


def _rubric_dimensions(weights: dict | None = None) -> list[dict]:
    weights = weights or {}
    return [
        {
            "dimension_code": code,
            "name": DIMENSION_NAMES[code],
            "weight": weights.get(code, 20),
            "section_types": DIMENSION_SECTION_TYPES[code],
        }
        for code in DIMENSION_CODES
    ]


def _parent(parent_id: str, content: str, section_type: str = "假设") -> dict:
    return {
        "parent_id": parent_id,
        "section_type": section_type,
        "content": content,
        "chunk_ids": [f"{parent_id}-00"],
        "review_id": "rv-1",
    }


def _reply(band: str, quote: str, chunk_id: str = "c-1", extra: dict | None = None) -> str:
    payload: dict = {"band": band, "chunk_id": chunk_id, "quote": quote}
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


class FakeChat:
    """假 chat：签名与 backend/app/llm/client.py 的 chat() 一致，按调用顺序回放响应。"""

    def __init__(self, responses) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def __call__(self, messages, temperature=0.2, *, transport=None) -> str:
        self.calls.append({"messages": messages, "temperature": temperature})
        if callable(self.responses):
            return self.responses(messages)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]


class RecordingRetriever:
    """假检索器：除 missing 里的维度外，每维给一段固定父块。"""

    def __init__(self, *, missing=(), outcomes: dict | None = None) -> None:
        self.requests: list = []
        self.missing = set(missing)
        self.outcomes = outcomes or {}

    def __call__(self, request):
        self.requests.append(request)
        code = request.dimension_code
        if code in self.missing:
            return {"status": BAND_INSUFFICIENT, "rounds": 2, "parents": [], "queries": ["q1", "q2"]}
        parents = self.outcomes.get(code)
        if parents is None:
            parents = [_parent(f"{code}-p1", EVIDENCE.get(code, "证据文本"))]
        return {"status": "命中", "rounds": 1, "parents": parents, "queries": ["q1"]}


def _run(*, chat=None, retriever=None, rubric_dimensions=None, constraints=None) -> dict:
    graph = build_review_graph(
        retriever=retriever,
        chat=chat,
        rubric_dimensions=rubric_dimensions,
        constraints=constraints,
    )
    review_id = create_review(PAPER_TEXT, graph=graph)
    config = {"configurable": {"thread_id": review_id}}
    sections = graph.get_state(config).values["sections"]
    return resume_review(review_id, sections, graph=graph)


def _only(code: str) -> RecordingRetriever:
    return RecordingRetriever(missing=set(DIMENSION_CODES) - {code})


def _constraints(contest_id: str) -> list[dict]:
    """只读赛题数据包里的 constraints.json，用于数据驱动的降档复核。"""
    payload = json.loads(
        (PROJECT_ROOT / "data" / "contests" / contest_id / "constraints.json").read_text(
            encoding="utf-8"
        )
    )
    return payload["constraints"]


# --- 用例 1-2：引用失败与证据不足都不进合计 ------------------------------------


def test_quote_not_a_substring_marks_citation_failure():
    chat = FakeChat([_reply(BAND_SUFFICIENT, "这句话不在任何父块里")])

    final = _run(chat=chat, retriever=_only("assumption"), rubric_dimensions=_rubric_dimensions())

    result = final["dimension_results"]["assumption"]
    assert result["status"] == STATUS_CITATION_FAILURE
    assert result["quote"] == "这句话不在任何父块里"
    assert final["score"]["total"] == 0
    assert all(item["dimension_code"] != "assumption" for item in final["score"]["weighted"])
    failure = [item for item in final["score"]["excluded"] if item["dimension_code"] == "assumption"]
    assert failure and failure[0]["reason"] == "引用失败不参与加权"


def test_insufficient_evidence_ignores_model_score():
    chat = FakeChat([_reply(BAND_INSUFFICIENT, "随便一句", extra={"score": 18, "weight": 30})])

    final = _run(chat=chat, retriever=_only("solution"), rubric_dimensions=_rubric_dimensions())

    result = final["dimension_results"]["solution"]
    assert result["band"] == BAND_INSUFFICIENT
    assert result["status"] == BAND_INSUFFICIENT
    assert final["score"]["total"] == 0
    assert result["dimension_code"] not in [item["dimension_code"] for item in final["score"]["weighted"]]


# --- 用例 3-5：权重只认量规数据 ------------------------------------------------


def test_matched_bands_enter_the_sum_by_rubric_weight():
    chat = FakeChat(
        [
            _reply(BAND_SUFFICIENT, QUOTES["assumption"]),
            _reply(BAND_BASIC, QUOTES["modeling"]),
            _reply(BAND_WEAK, QUOTES["solution"]),
        ]
    )
    retriever = RecordingRetriever(
        missing=set(DIMENSION_CODES) - {"assumption", "modeling", "solution"}
    )

    final = _run(chat=chat, retriever=retriever, rubric_dimensions=_rubric_dimensions())

    results = final["dimension_results"]
    assert [results[code]["status"] for code in ("assumption", "modeling", "solution")] == [
        BAND_SUFFICIENT,
        BAND_BASIC,
        BAND_WEAK,
    ]
    assert final["score"]["total"] == 60
    assert final["score"]["weight_sum"] == 60
    assert sum(item["contribution"] for item in final["score"]["weighted"]) == 60
    assert {item["dimension_code"] for item in final["score"]["weighted"]} == {
        "assumption",
        "modeling",
        "solution",
    }


def test_changing_rubric_weight_changes_total():
    dimensions = [
        {"dimension_code": "assumption", "weight": 20},
        {"dimension_code": "modeling", "weight": 20},
    ]
    results = [
        {"dimension_code": "assumption", "band": BAND_SUFFICIENT, "status": BAND_SUFFICIENT},
        {"dimension_code": "modeling", "band": BAND_BASIC, "status": BAND_BASIC},
    ]

    assert weighted_sum(dimensions, results)["total"] == 40

    dimensions[0]["weight"] = 30

    assert weighted_sum(dimensions, results)["total"] == 50


def test_model_weight_and_score_fields_are_ignored():
    dimensions = _rubric_dimensions()
    results = [
        {
            "dimension_code": "assumption",
            "band": BAND_SUFFICIENT,
            "status": BAND_SUFFICIENT,
            "weight": 99,
            "score": 100,
        }
    ]

    outcome = weighted_sum(dimensions, results)

    assert outcome["total"] == 20
    assert outcome["weighted"][0]["contribution"] == 20


# --- 用例 6-7：JSON 解析失败只重试一次 -----------------------------------------


def test_json_failure_twice_marks_failed_with_two_calls():
    chat = FakeChat(["这不是 JSON", "这仍然不是 JSON"])

    final = _run(chat=chat, retriever=_only("assumption"), rubric_dimensions=_rubric_dimensions())

    result = final["dimension_results"]["assumption"]
    assert result["status"] == STATUS_FAILURE
    assert result["reason"]
    assert result["band"] is None
    assert len(chat.calls) == 2, "解析失败只重试一次"
    assert final["score"]["total"] == 0
    failure = [item for item in final["score"]["excluded"] if item["dimension_code"] == "assumption"]
    assert failure and failure[0]["reason"] == "选档失败不参与加权"


def test_json_failure_then_success_scores_normally():
    chat = FakeChat(["不是 JSON", _reply(BAND_SUFFICIENT, QUOTES["assumption"])])

    final = _run(chat=chat, retriever=_only("assumption"), rubric_dimensions=_rubric_dimensions())

    result = final["dimension_results"]["assumption"]
    assert result["status"] == BAND_SUFFICIENT
    assert result["quote"] == QUOTES["assumption"]
    assert len(chat.calls) == 2
    assert final["score"]["total"] == 20


# --- 用例 8：没写调头圆弧的那一维是证据不足 ------------------------------------


def test_missing_turn_arc_dimension_is_evidence_insufficient():
    retriever = RecordingRetriever(
        missing={"constraint_check"},
        outcomes={
            code: [_parent(f"{code}-p1", EVIDENCE[code])]
            for code in DIMENSION_CODES
            if code != "constraint_check"
        },
    )
    chat = FakeChat(
        [
            _reply(BAND_SUFFICIENT, QUOTES["assumption"]),
            _reply(BAND_SUFFICIENT, QUOTES["modeling"]),
            _reply(BAND_SUFFICIENT, QUOTES["solution"]),
            _reply(BAND_SUFFICIENT, QUOTES["presentation"]),
        ]
    )

    final = _run(chat=chat, retriever=retriever, rubric_dimensions=_rubric_dimensions())

    result = final["dimension_results"]["constraint_check"]
    assert result["status"] == BAND_INSUFFICIENT
    assert DIMENSION_NAMES["constraint_check"] == "检验与题目约束"
    assert len(chat.calls) == 4, "检索为空的那一维不问模型"
    assert "constraint_check" not in [
        item["dimension_code"] for item in final["score"]["weighted"]
    ]
    assert final["score"]["total"] == 80


# --- 用例 9：确定性降档守卫（数据驱动，不写死题面字面量） ----------------------


def test_static_smoke_evidence_is_not_sufficient():
    constraints = _constraints("cumcm-2025-A")
    assert any(item["check_type"] == "mention" for item in constraints), "样例依赖 mention 约束"
    retriever = RecordingRetriever(
        missing=set(DIMENSION_CODES) - {"assumption"},
        outcomes={"assumption": [_parent("smoke-p1", STATIC_SMOKE_EVIDENCE)]},
    )
    chat = FakeChat([_reply(BAND_SUFFICIENT, STATIC_SMOKE_QUOTE)])

    final = _run(
        chat=chat,
        retriever=retriever,
        rubric_dimensions=_rubric_dimensions(),
        constraints=constraints,
    )

    result = final["dimension_results"]["assumption"]
    assert result["band"] != BAND_SUFFICIENT
    assert result["band"] == BAND_BASIC
    assert result["guard"]["downgraded"] is True
    assert result["guard"]["reasons"]
    assert result["status"] == BAND_BASIC


def test_guard_is_driven_by_constraint_data_not_by_literal_text():
    constraints = [
        {
            "name": "必须提到的自建条件",
            "check_type": "mention",
            "params": {"keywords": ["自建关键词"]},
            "section_types": ["假设"],
        }
    ]
    hidden = [
        {
            "name": "禁止提到假条件的目的",
            "check_type": "mention",
            "params": {"keywords": ["假关键词"]},
            "section_types": ["假设"],
        }
    ]

    downgraded = selection.apply_mention_guard(
        BAND_SUFFICIENT,
        evidence_text="只写了别的句子",
        constraints=constraints,
        dimension_section_types=["假设"],
    )
    kept = selection.apply_mention_guard(
        BAND_SUFFICIENT,
        evidence_text="这里出现了自建关键词",
        constraints=constraints,
        dimension_section_types=["假设"],
    )
    assert downgraded["band"] == BAND_BASIC
    assert kept["band"] == BAND_SUFFICIENT
    assert kept["checked"] == 1

    response = selection.apply_mention_guard(
        BAND_SUFFICIENT,
        evidence_text="这里出现了假关键词",
        constraints=hidden,
        dimension_section_types=["假设"],
    )
    assert response["band"] == BAND_SUFFICIENT, "关键词来自数据，不来自代码里的字面量"


# --- 用例 10：未注入 chat 时守住 P1 的闸门 -------------------------------------


def test_without_chat_keeps_placeholder_behavior():
    graph = build_review_graph(retriever=_only("assumption"))
    review_id = create_review(PAPER_TEXT, graph=graph)
    config = {"configurable": {"thread_id": review_id}}
    sections = graph.get_state(config).values["sections"]

    final = resume_review(review_id, sections, graph=graph)

    assert final["status"] == "完成"
    assert final["score_node_calls"] == 1
    assert final["retrievals"]["assumption"]["status"] == "命中"
    assert "score" not in final, "未注入 chat 时不选档、不加总"
    assert "dimension_results" not in final


def test_without_chat_resume_again_does_not_rescore():
    graph = build_review_graph()
    review_id = create_review(PAPER_TEXT, graph=graph)
    config = {"configurable": {"thread_id": review_id}}
    sections = graph.get_state(config).values["sections"]

    first = resume_review(review_id, sections, graph=graph)
    second = resume_review(review_id, sections, graph=graph)

    assert first["score_node_calls"] == 1
    assert second["score_node_calls"] == 1
    assert second["status"] == "完成"


def test_chat_without_rubric_dimensions_is_refused():
    with pytest.raises(ValueError):
        build_review_graph(chat=FakeChat([_reply(BAND_SUFFICIENT, QUOTES["assumption"])]))


# --- 加固断言 ------------------------------------------------------------------


def test_prompt_carries_at_most_four_parents():
    parents = [_parent(f"p-{index}", f"第 {index} 段证据") for index in range(6)]
    retriever = RecordingRetriever(
        missing=set(DIMENSION_CODES) - {"assumption"}, outcomes={"assumption": parents}
    )
    chat = FakeChat([_reply(BAND_SUFFICIENT, "第 0 段证据")])

    _run(chat=chat, retriever=retriever, rubric_dimensions=_rubric_dimensions())

    assert MAX_PARENTS == 4
    prompt = "\n".join(message["content"] for message in chat.calls[0]["messages"])
    assert "[4]" in prompt
    assert "[5]" not in prompt
    assert "第 5 段证据" not in prompt


def test_sources_have_no_http_and_no_llm_client():
    paths = sorted((PROJECT_ROOT / "backend" / "app" / "scoring").glob("*.py"))
    paths += sorted((PROJECT_ROOT / "backend" / "app" / "graph").glob("*.py"))
    assert paths
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in ("httpx", "requests", "urllib", "aiohttp", "openai", "backend.app.llm"):
            assert token not in source, f"{path}: {token}"
        for literal in ("3 m/s", "静止", "cumcm-2024", "cumcm-2025", "cumcm-2024-A"):
            assert literal not in source, f"{path}: {literal}"
    imported = {
        value.__name__
        for module in (review_graph, aggregate, selection)
        for value in vars(module).values()
        if isinstance(value, ModuleType)
    }
    assert not any(name.startswith("backend.app.llm") for name in imported)


def test_review_status_vocabulary_is_unchanged():
    assert tuple(REVIEW_STATUSES) == ("草稿解析", "待确认", "评分中", "完成", "失败")


def test_dimension_codes_come_from_the_shared_constants():
    assert tuple(DIMENSION_CODES) == (
        "assumption",
        "modeling",
        "solution",
        "constraint_check",
        "presentation",
    )
    chat = FakeChat([_reply(BAND_SUFFICIENT, QUOTES["assumption"])])

    final = _run(chat=chat, retriever=_only("assumption"), rubric_dimensions=_rubric_dimensions())

    seen = {item["dimension_code"] for item in final["score"]["weighted"]}
    seen |= {item["dimension_code"] for item in final["score"]["excluded"]}
    assert seen == set(DIMENSION_CODES)
    assert set(final["dimension_results"]) == set(DIMENSION_CODES)
