"""P19.2：评审记录进入现有父子块索引与检索路径。"""

from __future__ import annotations

from types import SimpleNamespace

import chromadb
import pytest

from backend.app.agent.retriever import PaperRetriever
from backend.app.chat import records
from backend.app.chat.retrieval import search_records
from backend.app.retrieve import parent_child
from backend.app.retrieve.parent_child import ChildChunk, ParentBlock


@pytest.fixture()
def vector_client(tmp_path):
    return chromadb.PersistentClient(path=str(tmp_path / "record-index"))


def _review(review_id="a" * 32, contest_id="contest-a", rubric_id="rubric-a", dimensions=None):
    return {
        "review_id": review_id,
        "contest_id": contest_id,
        "rubric_id": rubric_id,
        "dimensions": dimensions if dimensions is not None else [
            {"dimension_code": f"dim_{index}", "band": f"档位{index}", "quote": f"原句{index}"}
            for index in range(5)
        ],
        "change_list": [
            {"kind": "建议", "dimension_code": "dim_0", "text": "补充证据的说明"}
        ],
    }


def test_build_five_dimensions_creates_five_parent_child_pairs():
    parents, children = records.build_review_record(
        _review(), contest_id="contest-a", rubric_id="rubric-a"
    )
    assert len(parents) == len(children) == 5
    assert parents[0].parent_id == "rr-" + "a" * 32 + "-dim_0"
    assert children[0].chunk_id == parents[0].parent_id


def test_build_skips_dimension_without_band_or_quote():
    parents, children = records.build_review_record(
        _review(dimensions=[{"dimension_code": "empty", "band": "", "quote": ""}]),
        contest_id="contest-a", rubric_id="rubric-a",
    )
    assert parents == []
    assert children == []


def test_parent_content_has_dimension_band_quote_and_related_suggestions():
    review = _review(dimensions=[{"dimension_code": "assumption", "band": "基本", "quote": "引用句"}])
    review["change_list"] = [
        {"kind": "建议", "dimension_code": "assumption", "text": "补充证据的说明"}
    ]
    parents, _ = records.build_review_record(
        review,
        contest_id="contest-a", rubric_id="rubric-a",
    )
    content = parents[0].content
    assert "【维度】assumption" in content
    assert "【档位】基本" in content
    assert "【原句】引用句" in content
    assert "【关联建议】建议: 补充证据的说明" in content


def test_child_metadata_uses_review_record_and_single_section_type():
    _, children = records.build_review_record(
        _review(dimensions=[{"dimension_code": "assumption", "band": "基本", "quote": "引用句"}]),
        contest_id="contest-a", rubric_id="rubric-a",
    )
    child = children[0]
    metadata = parent_child.child_metadata(child)
    assert child.doc_type == "review_record"
    assert child.section_type == "评审记录"
    assert metadata["dimension_code"] == "assumption"
    assert metadata["contest_id"] == "contest-a"
    assert child.char_start == 0 and child.char_end == len(child.text)
    assert child.text.startswith("赛题 contest-a 记录 " + "a" * 32 + " 维度 assumption\n")


def test_index_review_record_is_idempotent(vector_client, monkeypatch):
    review = _review(dimensions=[{"dimension_code": "assumption", "band": "基本", "quote": "引用句"}])
    monkeypatch.setattr(records.report_store, "load_review", lambda review_id, session=None: review)
    monkeypatch.setattr(records.parent_child, "save_parents", lambda parents: len(list(parents)))
    monkeypatch.setattr(
        "backend.app.llm.client.embed",
        lambda texts: [[0.1] * 8 for _ in texts],
    )
    first = records.index_review_record(review["review_id"], client=vector_client)
    second = records.index_review_record(review["review_id"], client=vector_client)
    assert first == second == 1
    assert parent_child.get_collection(vector_client).count() == 1


def test_delete_review_record_removes_only_review_record_children(vector_client, monkeypatch):
    review = _review(dimensions=[{"dimension_code": "assumption", "band": "基本", "quote": "引用句"}])
    monkeypatch.setattr(records.report_store, "load_review", lambda review_id, session=None: review)
    monkeypatch.setattr(records.parent_child, "save_parents", lambda parents: len(list(parents)))
    monkeypatch.setattr(records, "_delete_parent_blocks", lambda review_id: None)
    monkeypatch.setattr("backend.app.llm.client.embed", lambda texts: [[0.1] * 8 for _ in texts])
    records.index_review_record(review["review_id"], client=vector_client)
    records.delete_review_record(review["review_id"], client=vector_client)
    assert parent_child.get_collection(vector_client).count() == 0


def test_doc_type_whitelist_has_six_and_rejects_near_miss():
    assert len(parent_child.DOC_TYPES) == 6
    assert parent_child.DOC_TYPES[-1] == "review_record"
    with pytest.raises(parent_child.DocTypeError):
        parent_child._require_doc_type("review_recordd")


def test_where_omits_empty_rubric_and_keeps_real_rubric():
    empty = parent_child._where("contest-a", "")
    concrete = parent_child._where("contest-a", "rubric-a")
    assert all("rubric_id" not in clause for clause in empty["$and"])
    assert {"rubric_id": "rubric-a"} in concrete["$and"]


def test_search_records_passes_contest_scope_and_parses_dimensions():
    rows = {
        "contest-a": [
            ParentBlock(parent_id=f"rr-{'a' * 32}-dim_{index}", section_type="评审记录", content=f"结果{index}")
            for index in range(2)
        ],
        "contest-b": [
            ParentBlock(parent_id=f"rr-{'b' * 32}-dim_0", section_type="评审记录", content="另题结果")
        ],
    }
    calls = []

    def retrieve_fn(query, **kwargs):
        calls.append(kwargs)
        return rows[kwargs["contest_id"]]

    found = search_records("假设证据", contest_id="contest-a", retrieve_fn=retrieve_fn)
    assert len(found) == 2
    assert all(item["review_id"] == "a" * 32 for item in found)
    assert {item["dimension_code"] for item in found} == {"dim_0", "dim_1"}
    assert calls[0]["doc_types"] == ("review_record",)
    assert calls[0]["rubric_id"] == "" and calls[0]["review_id"] is None


def test_search_records_empty_is_normal_and_paper_retriever_forwards_doc_types():
    assert search_records("没有命中", contest_id="contest-a", retrieve_fn=lambda *_a, **_k: []) == []
    seen = {}

    def retrieve_fn(query, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(status="ok", parents=[])

    retriever = PaperRetriever(contest_id="contest-a", doc_types=("review_record",), retrieve_fn=retrieve_fn)
    assert retriever.invoke("检索问题") == []
    assert seen["doc_types"] == ("review_record",)

