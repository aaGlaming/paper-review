# 客户端契约测试。
# 全程用 httpx.MockTransport 注入，不访问网络，不读取真实 .env。
# 断言：对话走 /chat/completions、嵌入走 /embeddings；只读约定字段；
# 响应缺少约定字段时抛错，不返回空字符串或空列表冒充结果。

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.llm.client import (  # noqa: E402
    LLMConfigError,
    LLMResponseError,
    chat,
    embed,
)

BASE_URL = "https://example.invalid/v1"
API_KEY = "sk-unit-SECRET-4d7f"
CHAT_MODEL = "unit-chat-model"
EMBEDDING_MODEL = "unit-embed-model"

MESSAGES = [{"role": "user", "content": "这是第一段论文正文"}]


def _set_env(monkeypatch):
    """把四个环境变量设成测试值。值不是真实密钥，也不指向真实服务。"""
    monkeypatch.setenv("LLM_BASE_URL", BASE_URL)
    monkeypatch.setenv("LLM_API_KEY", API_KEY)
    monkeypatch.setenv("LLM_MODEL", CHAT_MODEL)
    monkeypatch.setenv("EMBEDDING_MODEL", EMBEDDING_MODEL)


def _transport(handler):
    """包装 MockTransport，同时记录收到的请求。"""
    seen: list[httpx.Request] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return httpx.MockTransport(_handle), seen


def _ok(payload, status_code: int = 200):
    return lambda request: httpx.Response(status_code, json=payload)


def _chat_payload(content):
    """带厂商常见字段的完整对话响应。"""
    return {
        "id": "chatcmpl-unit-1",
        "object": "chat.completion",
        "created": 1760000000,
        "model": CHAT_MODEL,
        "system_fingerprint": "fp_unit",
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }


def _embed_payload(vectors):
    return {
        "object": "list",
        "model": EMBEDDING_MODEL,
        "usage": {"prompt_tokens": 3, "total_tokens": 3},
        "data": [
            {"object": "embedding", "index": index, "embedding": vector}
            for index, vector in enumerate(vectors)
        ],
    }


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def test_chat_uses_post_chat_completions(monkeypatch):
    _set_env(monkeypatch)
    transport, seen = _transport(_ok(_chat_payload("第一条正文")))

    chat(MESSAGES, transport=transport)

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert request.url.path.endswith("/chat/completions")
    assert str(request.url).startswith(BASE_URL)


def test_chat_sends_bearer_authorization_header(monkeypatch):
    _set_env(monkeypatch)
    transport, seen = _transport(_ok(_chat_payload("第一条正文")))

    chat(MESSAGES, transport=transport)

    assert seen[0].headers.get("authorization") == f"Bearer {API_KEY}"


def test_chat_body_has_model_messages_and_default_temperature(monkeypatch):
    _set_env(monkeypatch)
    transport, seen = _transport(_ok(_chat_payload("第一条正文")))

    chat(MESSAGES, transport=transport)

    body = _body(seen[0])
    assert body["model"] == CHAT_MODEL
    assert body["messages"] == MESSAGES
    assert body["temperature"] == 0.2


def test_chat_temperature_is_forwarded_when_given(monkeypatch):
    _set_env(monkeypatch)
    transport, seen = _transport(_ok(_chat_payload("第一条正文")))

    chat(MESSAGES, temperature=0.75, transport=transport)

    assert _body(seen[0])["temperature"] == 0.75


def test_chat_returns_only_first_choice_content(monkeypatch):
    _set_env(monkeypatch)
    payload = {
        "id": "chatcmpl-unit-2",
        "content": "顶层 content 不是结果",
        "text": "厂商私有字段不是结果",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "唯一正确的正文",
                    "reasoning_content": "思考过程不是结果",
                    "audio": {"data": "私有字段"},
                },
            },
            {
                "index": 1,
                "message": {"role": "assistant", "content": "第二条不是结果"},
            },
        ],
    }
    transport, _seen = _transport(_ok(payload))

    result = chat(MESSAGES, transport=transport)

    assert isinstance(result, str)
    assert result == "唯一正确的正文"


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "chatcmpl-unit-3"},
        {"choices": []},
        {"choices": [{"index": 0}]},
        {"choices": [{"message": {"role": "assistant"}}]},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": 42}}]},
        {"choices": "not-a-list"},
    ],
)
def test_chat_rejects_malformed_payloads(monkeypatch, payload):
    _set_env(monkeypatch)
    transport, _seen = _transport(_ok(payload))

    with pytest.raises(LLMResponseError) as excinfo:
        chat(MESSAGES, transport=transport)

    assert str(excinfo.value).strip(), "错误信息不得为空"


def test_embed_posts_input_list_with_embedding_model(monkeypatch):
    _set_env(monkeypatch)
    texts = ["第二段", "第一段", "第三段"]
    transport, seen = _transport(_ok(_embed_payload([[0.2], [0.1], [0.3]])))

    embed(texts, transport=transport)

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert request.url.path.endswith("/embeddings")
    assert str(request.url).startswith(BASE_URL)
    body = _body(request)
    assert body["model"] == EMBEDDING_MODEL
    assert body["model"] != CHAT_MODEL
    assert body["input"] == texts


def test_embed_returns_vectors_in_input_order(monkeypatch):
    _set_env(monkeypatch)
    texts = ["第二段", "第一段", "第三段"]
    vectors = [[0.2, 0.4], [1, 2], [0.3]]
    transport, _seen = _transport(_ok(_embed_payload(vectors)))

    result = embed(texts, transport=transport)

    assert len(result) == len(texts)
    assert result == [[0.2, 0.4], [1.0, 2.0], [0.3]]
    assert all(isinstance(value, float) for row in result for value in row)


@pytest.mark.parametrize(
    "payload",
    [
        {"object": "list"},
        {"data": "not-a-list"},
        {"data": [{"index": 0}]},
        {"data": [{"embedding": None}]},
        {"data": [{"embedding": "0.1"}]},
        {"data": [{"embedding": [0.1]}]},
    ],
)
def test_embed_rejects_malformed_payloads(monkeypatch, payload):
    _set_env(monkeypatch)
    transport, _seen = _transport(_ok(payload))

    with pytest.raises(LLMResponseError) as excinfo:
        embed(["第一段", "第二段"], transport=transport)

    assert str(excinfo.value).strip(), "错误信息不得为空"


def test_missing_env_raises_config_error_without_secret(monkeypatch):
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        _set_env(monkeypatch)
        monkeypatch.delenv(name)
        transport, _seen = _transport(_ok(_chat_payload("正文")))
        with pytest.raises(LLMConfigError) as excinfo:
            chat(MESSAGES, transport=transport)
        assert API_KEY not in str(excinfo.value)

    for name in ("LLM_BASE_URL", "LLM_API_KEY", "EMBEDDING_MODEL"):
        _set_env(monkeypatch)
        monkeypatch.delenv(name)
        transport, _seen = _transport(_ok(_embed_payload([[0.1]])))
        with pytest.raises(LLMConfigError) as excinfo:
            embed(["第一段"], transport=transport)
        assert API_KEY not in str(excinfo.value)


def test_transport_error_is_retried_once(monkeypatch):
    _set_env(monkeypatch)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("连接失败", request=request)
        return httpx.Response(200, json=_chat_payload("重试后的正文"))

    result = chat(MESSAGES, transport=httpx.MockTransport(handler))

    assert calls["count"] == 2
    assert result == "重试后的正文"
