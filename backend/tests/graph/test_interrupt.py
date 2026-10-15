# 章节确认测试。
# 全程不调用云端模型、不访问网络：本文件不 import backend.app.llm.client。
# 断言：未确认不进入评分；同一 review_id 重建图后仍停在待确认且不重算章节树；
# 空文档不产生 review_id；状态词表封闭在五个值内。
# 夹具是本文件内部的内联 Markdown 字符串，不读 data/samples/。

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest
from langgraph.checkpoint.memory import InMemorySaver

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.graph import review_graph  # noqa: E402
from backend.app.graph.review_graph import (  # noqa: E402
    REVIEW_STATUSES,
    SECTION_TYPES,
    UNCLASSIFIED_SECTION_TYPE,
    build_review_graph,
    create_review,
    resume_review,
)

PAPER_TEXT = "\n".join(
    [
        "# 板凳龙运动分析",
        "",
        "## 摘要",
        "本文给出板凳龙的运动学模型。",
        "",
        "## 一、模型假设",
        "忽略板凳宽度，把手视为质点。",
        "",
        "## 二、模型的建立",
        "给出螺距与龙头速度的关系。",
        "",
        "## 三、模型求解",
        "用迭代法逐段求解。",
        "",
        "## 四、结果分析",
        "总运动时间为 412 s。",
        "",
        "## 五、模型检验",
        "把手速度不超过 2 m/s。",
        "",
        "## 参考文献",
        "[1] 自建样例，不是官方答案。",
    ]
)

UNTYPED_TEXT = "\n".join(
    [
        "开场文字，没有任何标题。",
        "",
        "# 只有一个标题",
        "正文一。",
        "",
        "## 摘要",
        "正文二。",
    ]
)


def _config(review_id: str) -> dict:
    return {"configurable": {"thread_id": review_id}}


def _new_graph():
    return build_review_graph(InMemorySaver())


def _state(graph, review_id: str) -> dict:
    return graph.get_state(_config(review_id)).values


def _types_by_title(sections) -> dict:
    return {section["title"]: section["section_type"] for section in sections}


def _corrected_sections(sections) -> list:
    """人工把「模型的建立」改判为假设，并换掉标题。重新解析不可能得到这个结果。"""
    corrected = [dict(section) for section in sections]
    for section in corrected:
        if section["title"] == "二、模型的建立":
            section["title"] = "二、模型假设（人工确认）"
            section["section_type"] = "假设"
    return corrected


def test_parse_classifies_six_section_types():
    graph = _new_graph()
    review_id = create_review(PAPER_TEXT, graph=graph)

    sections = _state(graph, review_id)["sections"]
    types = _types_by_title(sections)

    assert types["一、模型假设"] == "假设"
    assert types["二、模型的建立"] == "模型"
    assert types["三、模型求解"] == "求解"
    assert types["四、结果分析"] == "结果"
    assert types["五、模型检验"] == "检验"
    assert types["参考文献"] == "参考文献"
    assert set(types.values()) <= {*SECTION_TYPES, UNCLASSIFIED_SECTION_TYPE}
    assert len(SECTION_TYPES) == 6
    assert types["摘要"] == UNCLASSIFIED_SECTION_TYPE


def test_create_review_stops_at_pending_confirmation():
    graph = _new_graph()
    review_id = create_review(PAPER_TEXT, graph=graph)

    state = _state(graph, review_id)

    assert isinstance(review_id, str) and review_id
    assert state["review_id"] == review_id
    assert state["status"] == "待确认"
    assert state["confirmed"] is False
    assert state["score_node_calls"] == 0


def test_graph_pauses_on_confirm_node():
    graph = _new_graph()
    review_id = create_review(PAPER_TEXT, graph=graph)

    snapshot = graph.get_state(_config(review_id))

    assert snapshot.next == ("confirm",)


def test_interrupt_payload_carries_parsed_sections():
    graph = _new_graph()
    review_id = create_review(PAPER_TEXT, graph=graph)

    snapshot = graph.get_state(_config(review_id))
    payload = snapshot.tasks[0].interrupts[0].value

    assert payload["review_id"] == review_id
    assert payload["sections"] == snapshot.values["sections"]
    assert payload["sections"]


def test_rebuilt_graph_resumes_from_checkpoint_without_reparsing():
    saver = InMemorySaver()
    graph = build_review_graph(saver)
    review_id = create_review(PAPER_TEXT, graph=graph)
    first_sections = _state(graph, review_id)["sections"]

    rebuilt = build_review_graph(saver)
    snapshot = rebuilt.get_state(_config(review_id))

    assert snapshot.next == ("confirm",)
    assert snapshot.values["confirmed"] is False
    assert snapshot.values["status"] == "待确认"
    assert snapshot.values["score_node_calls"] == 0
    assert snapshot.values["sections"] == first_sections
    assert snapshot.values["parse_node_calls"] == 1


def test_resume_applies_confirmed_sections_and_scores_once():
    saver = InMemorySaver()
    graph = build_review_graph(saver)
    review_id = create_review(PAPER_TEXT, graph=graph)
    corrected = _corrected_sections(_state(graph, review_id)["sections"])

    final = resume_review(review_id, corrected, graph=graph)

    assert final["status"] == "完成"
    assert final["confirmed"] is True
    assert final["score_node_calls"] == 1
    assert final["parse_node_calls"] == 1
    assert final["sections"] == corrected
    assert _state(graph, review_id)["sections"] == corrected
    assert graph.get_state(_config(review_id)).next == ()


def test_empty_paper_raises_and_creates_no_review():
    assert issubclass(review_graph.EmptyPaperError, ValueError)

    saver = InMemorySaver()
    graph = build_review_graph(saver)
    for text in ("", "   \n\t\n  "):
        with pytest.raises(ValueError) as excinfo:
            create_review(text, review_id="empty-review", graph=graph)
        assert str(excinfo.value).strip()

    with pytest.raises(ValueError):
        create_review("", graph=graph)

    snapshot = graph.get_state(_config("empty-review"))
    assert snapshot.values == {}
    assert snapshot.next == ()


def test_resume_after_completion_does_not_score_again():
    saver = InMemorySaver()
    graph = build_review_graph(saver)
    review_id = create_review(PAPER_TEXT, graph=graph)
    corrected = _corrected_sections(_state(graph, review_id)["sections"])

    first = resume_review(review_id, corrected, graph=graph)
    second = resume_review(review_id, corrected, graph=graph)

    assert first["score_node_calls"] == 1
    assert second["score_node_calls"] == 1
    assert second["status"] == "完成"
    assert second["sections"] == corrected


def test_status_vocabulary_is_closed():
    assert tuple(REVIEW_STATUSES) == ("草稿解析", "待确认", "评分中", "完成", "失败")
    assert "已获奖" not in REVIEW_STATUSES
    assert not any("奖" in status for status in REVIEW_STATUSES)

    graph = _new_graph()
    review_id = create_review(PAPER_TEXT, graph=graph)
    seen = [_state(graph, review_id)["status"]]
    seen.append(
        resume_review(
            review_id,
            _corrected_sections(_state(graph, review_id)["sections"]),
            graph=graph,
        )["status"]
    )

    assert set(seen) <= set(REVIEW_STATUSES)


def test_untyped_headings_fall_back_without_a_seventh_type():
    graph = _new_graph()
    review_id = create_review(UNTYPED_TEXT, graph=graph)

    sections = _state(graph, review_id)["sections"]
    types = _types_by_title(sections)

    assert types["只有一个标题"] == UNCLASSIFIED_SECTION_TYPE
    assert types["摘要"] == UNCLASSIFIED_SECTION_TYPE
    assert sections[0]["section_type"] == UNCLASSIFIED_SECTION_TYPE
    assert set(types.values()) <= {*SECTION_TYPES, UNCLASSIFIED_SECTION_TYPE}
    assert UNCLASSIFIED_SECTION_TYPE not in SECTION_TYPES


def test_module_uses_no_http_and_no_llm_client():
    source = Path(review_graph.__file__).read_text(encoding="utf-8")

    for token in ("httpx", "requests", "urllib", "aiohttp", "openai", "backend.app.llm"):
        assert token not in source

    # 本模块自己导入的模块里没有模型客户端：只看本模块的命名空间，
    # 不查整个 pytest 会话的 sys.modules，否则跟别的测试文件同跑会误报。
    imported = {
        value.__name__
        for value in vars(review_graph).values()
        if isinstance(value, ModuleType)
    }
    assert not any(name.startswith("backend.app.llm") for name in imported)
