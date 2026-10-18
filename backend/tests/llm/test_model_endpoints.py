from __future__ import annotations

import json

import httpx
import pytest

from backend.app.llm import client


def test_embed_uses_independent_base_url_and_api_key(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://chat.example/v1")
    monkeypatch.setenv("LLM_API_KEY", "chat-test-key")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embed.example/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embed-test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": [{"embedding": [0.2, 0.4]}]})

    client.embed(["paper passage"], transport=httpx.MockTransport(handler))

    assert str(seen[0].url) == "https://embed.example/v1/embeddings"
    assert seen[0].headers["authorization"] == "Bearer embed-test-key"
    assert json.loads(seen[0].content)["model"] == "BAAI/bge-m3"


def test_embed_falls_back_to_chat_base_url_and_key(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://chat.example/v1")
    monkeypatch.setenv("LLM_API_KEY", "chat-test-key")
    monkeypatch.delenv("EMBEDDING_BASE_URL")
    monkeypatch.delenv("EMBEDDING_API_KEY")
    monkeypatch.setenv("EMBEDDING_MODEL", "embedding-model")
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": [{"embedding": [1]}]})

    client.embed(["paper passage"], transport=httpx.MockTransport(handler))

    assert str(seen[0].url) == "https://chat.example/v1/embeddings"
    assert seen[0].headers["authorization"] == "Bearer chat-test-key"


def test_rerank_sends_cohere_style_payload_and_returns_sorted_indices(monkeypatch):
    rerank = getattr(client, "rerank", None)
    assert callable(rerank), "client.py must expose the only HTTP rerank entry point"
    monkeypatch.setenv("RERANK_BASE_URL", "https://rank.example/v1")
    monkeypatch.setenv("RERANK_API_KEY", "rank-test-key")
    monkeypatch.setenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"results": [
            {"index": 1, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.2},
        ]})

    indices = rerank("query", ["first", "second"], transport=httpx.MockTransport(handler))

    assert indices == [1, 0]
    assert str(seen[0].url) == "https://rank.example/v1/rerank"
    assert seen[0].headers["authorization"] == "Bearer rank-test-key"
    assert json.loads(seen[0].content) == {
        "model": "BAAI/bge-reranker-v2-m3",
        "query": "query",
        "documents": ["first", "second"],
    }


@pytest.mark.parametrize("results", [
    [{"index": 0, "relevance_score": 0.8}],
    [{"index": 0, "relevance_score": 0.8}, {"index": 9, "relevance_score": 0.2}],
])
def test_rerank_rejects_missing_or_out_of_range_indices(monkeypatch, results):
    rerank = getattr(client, "rerank", None)
    assert callable(rerank), "client.py must expose the only HTTP rerank entry point"
    monkeypatch.setenv("RERANK_BASE_URL", "https://rank.example/v1")
    monkeypatch.setenv("RERANK_API_KEY", "rank-test-key")
    monkeypatch.setenv("RERANK_MODEL", "rank-model")

    with pytest.raises(client.LLMResponseError):
        rerank("query", ["first", "second"], transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"results": results})
        ))

