from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.llm.client import LLMResponseError, chat_with_tools  # noqa: E402

BASE_URL = "https://example.invalid/v1"
API_KEY = "sk-unit-SECRET-4d7f"
CHAT_MODEL = "unit-chat-model"
MESSAGES = [{"role": "user", "content": "调用工具"}]
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "原样返回",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }
]


def _set_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", BASE_URL)
    monkeypatch.setenv("LLM_API_KEY", API_KEY)
    monkeypatch.setenv("LLM_MODEL", CHAT_MODEL)


def _transport(handler):
    seen: list[httpx.Request] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return httpx.MockTransport(_handle), seen


def _ok(payload, status_code: int = 200):
    return lambda request: httpx.Response(status_code, json=payload)


def _tool_payload(arguments: str = '{"text":"hello"}'):
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "echo", "arguments": arguments},
                        }
                    ],
                },
            }
        ]
    }


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def test_chat_with_tools_parses_calls_and_sends_openai_tool_shape(monkeypatch):
    _set_env(monkeypatch)
    transport, seen = _transport(_ok(_tool_payload()))

    result = chat_with_tools(MESSAGES, TOOLS, transport=transport)

    assert result == {
        "content": "",
        "tool_calls": [{"id": "call-1", "name": "echo", "arguments": {"text": "hello"}}],
        "finish_reason": "tool_calls",
    }
    request_body = _body(seen[0])
    assert request_body["tools"] == TOOLS
    assert request_body["tool_choice"] == "auto"
    assert request_body["messages"] == MESSAGES


def test_chat_with_tools_rejects_invalid_arguments_without_echoing_them(monkeypatch):
    _set_env(monkeypatch)
    secret_arguments = '{"token":"private-full-arguments"'
    transport, _seen = _transport(_ok(_tool_payload(secret_arguments)))

    with pytest.raises(LLMResponseError) as excinfo:
        chat_with_tools(MESSAGES, TOOLS, transport=transport)

    assert "tool_calls[0].arguments" in str(excinfo.value)
    assert secret_arguments not in str(excinfo.value)


def test_chat_with_tools_returns_content_when_no_calls_and_rejects_empty_tools(monkeypatch):
    _set_env(monkeypatch)
    payload = {"choices": [{"finish_reason": "stop", "message": {"content": "ordinary answer"}}]}
    transport, _seen = _transport(_ok(payload))

    result = chat_with_tools(MESSAGES, TOOLS, transport=transport)

    assert result == {"content": "ordinary answer", "tool_calls": [], "finish_reason": "stop"}
    with pytest.raises(ValueError, match="tools 不能为空"):
        chat_with_tools(MESSAGES, [], transport=transport)


def test_chat_with_tools_does_not_retry_http_500(monkeypatch):
    _set_env(monkeypatch)
    transport, seen = _transport(_ok({"error": "server error"}, status_code=500))

    with pytest.raises(LLMResponseError):
        chat_with_tools(MESSAGES, TOOLS, transport=transport)

    assert len(seen) == 1


def test_chat_with_tools_retries_transport_error_once(monkeypatch):
    _set_env(monkeypatch)

    def fail_connection(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    transport, seen = _transport(fail_connection)

    with pytest.raises(LLMResponseError):
        chat_with_tools(MESSAGES, TOOLS, transport=transport)

    assert len(seen) == 2


def test_chat_with_tools_never_returns_or_reports_api_key(monkeypatch):
    _set_env(monkeypatch)
    transport, _seen = _transport(_ok(_tool_payload()))
    result = chat_with_tools(MESSAGES, TOOLS, transport=transport)
    assert API_KEY not in repr(result)

    failed_transport, _failed_seen = _transport(_ok({}, status_code=500))
    with pytest.raises(LLMResponseError) as excinfo:
        chat_with_tools(MESSAGES, TOOLS, transport=failed_transport)
    assert API_KEY not in str(excinfo.value)
