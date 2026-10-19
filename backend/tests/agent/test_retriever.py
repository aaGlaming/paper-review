from types import SimpleNamespace

import pytest

from backend.app.agent.retriever import PaperRetriever


def parent(parent_id: str, *, review_id: str = "review-1"):
    return SimpleNamespace(
        parent_id=parent_id,
        content=f"full content for {parent_id}",
        section_type="method",
        chunk_ids=(f"{parent_id}-chunk-1", f"{parent_id}-chunk-2"),
        review_id=review_id,
    )


def test_retriever_returns_documents_with_required_metadata():
    captured = {}

    def retrieve(query, **kwargs):
        captured["query"] = query
        captured["kwargs"] = kwargs
        return SimpleNamespace(status="命中", parents=(parent("p1"), parent("p2")))

    retriever = PaperRetriever(
        contest_id="contest-1",
        rubric_id="rubric-1",
        review_id="review-1",
        dimension_code="D1",
        section_types=("method", "result"),
        retrieve_fn=retrieve,
    )

    documents = retriever.invoke("evidence query")

    assert len(documents) == 2
    assert documents[0].page_content == "full content for p1"
    assert documents[0].metadata == {
        "parent_id": "p1",
        "section_type": "method",
        "chunk_ids": ("p1-chunk-1", "p1-chunk-2"),
        "review_id": "review-1",
    }
    assert documents[1].metadata["parent_id"] == "p2"
    assert captured == {
        "query": "evidence query",
        "kwargs": {
            "contest_id": "contest-1",
            "rubric_id": "rubric-1",
            "review_id": "review-1",
            "dimension_code": "D1",
            "section_types": ("method", "result"),
        },
    }


def test_retriever_returns_empty_for_insufficient_or_missing_parents():
    for result in (
        SimpleNamespace(status="证据不足", parents=(parent("ignored"),)),
        SimpleNamespace(status="命中", parents=()),
    ):
        retriever = PaperRetriever(retrieve_fn=lambda query, **kwargs: result)
        assert retriever.invoke("query") == []


def test_retriever_requires_injected_retrieve_function():
    retriever = PaperRetriever()

    with pytest.raises(ValueError, match="retrieve_fn.*注入|注入.*retrieve_fn"):
        retriever.invoke("query")
