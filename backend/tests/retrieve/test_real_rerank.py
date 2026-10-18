from __future__ import annotations

import pytest

from backend.app.retrieve import rerank as rerank_module


def test_build_http_reranker_maps_ranked_documents_back_to_parent_ids(monkeypatch):
    monkeypatch.setenv("RERANK_BASE_URL", "https://rank.example/v1")
    monkeypatch.setenv("RERANK_API_KEY", "rank-test-key")
    monkeypatch.setenv("RERANK_MODEL", "rank-model")
    client = rerank_module.build_rerank_client(
        "http",
        parent_contents={"p1": "first content", "p2": "second content"},
        rank=lambda query, documents: [1, 0],
    )

    assert client.rerank("query", ["p1", "p2"]) == ["p2", "p1"]


def test_build_http_reranker_rejects_unconfigured_keys(monkeypatch):
    for key in ("RERANK_BASE_URL", "RERANK_API_KEY", "RERANK_MODEL"):
        monkeypatch.setenv(key, "")

    with pytest.raises(NotImplementedError):
        rerank_module.build_rerank_client("http")


def test_build_http_reranker_rejects_incomplete_or_invalid_rankings(monkeypatch):
    monkeypatch.setenv("RERANK_BASE_URL", "https://rank.example/v1")
    monkeypatch.setenv("RERANK_API_KEY", "rank-test-key")
    monkeypatch.setenv("RERANK_MODEL", "rank-model")
    client = rerank_module.build_rerank_client(
        "http", parent_contents={"p1": "first", "p2": "second"}, rank=lambda *_: [0]
    )

    with pytest.raises(ValueError):
        client.rerank("query", ["p1", "p2"])
