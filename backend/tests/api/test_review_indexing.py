from __future__ import annotations

from importlib import import_module
from contextlib import contextmanager
from types import SimpleNamespace

routes = import_module("backend.app.api.routes")


def _index_dependencies(monkeypatch, embed):
    from backend.app.llm import client as llm_client
    from backend.app.retrieve import parent_child
    from backend.app.retrieve import models as parent_models

    saved = []
    indexed = []

    class Repo:
        def save_parents(self, parents):
            saved.extend(parents)
            return len(parents)

    monkeypatch.setattr(parent_models, "create_parent_schema", lambda: None)
    monkeypatch.setattr(parent_child, "ParentRepository", lambda: Repo())
    monkeypatch.setattr(parent_child, "index_children", lambda children, **kwargs: indexed.extend(children))
    monkeypatch.setattr(llm_client, "embed", embed)
    return saved, indexed


def test_review_index_builds_mysql_parents_and_chroma_children_with_embeddings(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embed.example/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embed-test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    calls = []
    saved, indexed = _index_dependencies(monkeypatch, lambda texts: calls.append(texts) or [[0.1, 0.2] for _ in texts])

    result = routes._prepare_review_index(
        review_id="review-1",
        contest_id="contest-1",
        rubric_id="rubric-1",
        sections=[{"title": "模型", "section_type": "模型", "content": "模型正文证据"}],
    )

    assert len(saved) == 1 and saved[0].content == "模型正文证据"
    assert len(indexed) == 1 and indexed[0].embedding == (0.1, 0.2)
    assert calls == [["模型正文证据"]]
    assert result["vector_enabled"] is True


def test_review_index_keeps_mysql_fallback_when_embedding_fails(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embed.example/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embed-test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    def fail_embedding(_texts):
        raise RuntimeError("offline")

    saved, indexed = _index_dependencies(monkeypatch, fail_embedding)
    result = routes._prepare_review_index(
        review_id="review-2",
        contest_id="contest-1",
        rubric_id="rubric-1",
        sections=[{"title": "模型", "section_type": "模型", "content": "模型正文证据"}],
    )

    assert len(saved) == 1
    assert saved[0].chunk_ids == ("review-2-0000-00",)
    assert indexed == []
    assert result["vector_enabled"] is False


def test_review_index_supplies_historical_candidate_contents_to_reranker(monkeypatch):
    from backend.app.importing import db

    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embed.example/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embed-test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    _index_dependencies(monkeypatch, lambda texts: [[0.1, 0.2] for _ in texts])

    class Session:
        def __init__(self):
            self.calls = 0

        def scalars(self, _statement):
            self.calls += 1
            if self.calls == 1:
                return ["review-1", "review-history"]
            return [
                SimpleNamespace(parent_id="review-history-0001", content="historical paper content"),
            ]

    fake_session = Session()

    @contextmanager
    def fake_session_scope():
        yield fake_session

    monkeypatch.setattr(db, "session_scope", fake_session_scope)

    result = routes._prepare_review_index(
        review_id="review-1",
        contest_id="contest-1",
        rubric_id="rubric-1",
        sections=[{"title": "模型", "section_type": "模型", "content": "current paper content"}],
    )

    assert result["parent_contents"]["review-history-0001"] == "historical paper content"


def test_retriever_uses_confirmed_sections_when_graph_request_has_no_section_types(monkeypatch):
    from contextlib import contextmanager

    from backend.app.graph.review_graph import RetrieveRequest
    from backend.app.importing import db
    from backend.app.retrieve import three_route

    _index_dependencies(monkeypatch, lambda _texts: [])

    @contextmanager
    def empty_session_scope():
        class Session:
            def scalars(self, _statement):
                return []

        yield Session()

    monkeypatch.setattr(db, "session_scope", empty_session_scope)
    calls = []
    monkeypatch.setattr(
        three_route,
        "retrieve_dimension",
        lambda query, **kwargs: calls.append((query, kwargs)) or {"status": "命中", "parents": []},
    )
    index = routes._prepare_review_index(
        review_id="review-3",
        contest_id="contest-1",
        rubric_id="rubric-1",
        sections=[{"title": "假设", "section_type": "假设", "content": "假设正文"}],
        dimensions=[{
            "dimension_code": "assumption",
            "name": "模型假设",
            "section_types": ["假设", "模型"],
        }],
    )

    index["retriever"](
        RetrieveRequest("review-3", "assumption", "contest-1", "rubric-1", ())
    )

    assert len(calls) == 1
    assert calls[0][1]["section_types"] == ("假设",)
