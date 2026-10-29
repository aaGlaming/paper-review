"""全项目唯一的云端模型客户端。

约定见 docs/开发任务拆解与迭代流程.md 第 4.5 节：
对话 POST {LLM_BASE_URL}/chat/completions，只读 choices[0].message.content；
嵌入 POST {EMBEDDING_BASE_URL}/embeddings（缺省回落 LLM_BASE_URL），只读 data[].embedding；
重排 POST {RERANK_BASE_URL}/rerank，返回按 relevance_score 排序的候选下标。
其他模块不得自己发 HTTP，也不得读取厂商私有字段。
配置只从环境变量读，密钥不打印、不回显、不落盘。
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Sequence
from typing import Any

import httpx

from ..observability import log_event
from ..observability.metrics import observe_llm

__all__ = ["chat", "embed", "rerank", "LLMConfigError", "LLMResponseError", "chat_with_tools"]

DEFAULT_TEMPERATURE = 0.2
_TIMEOUT_SECONDS = 30.0
_MAX_ATTEMPTS = 2  # 首次请求 + 网络层最多重试 1 次


class LLMConfigError(RuntimeError):
    """环境变量缺失。错误信息只含变量名，不含变量值。"""


class LLMResponseError(RuntimeError):
    """响应结构与约定不符，或网络层重试后仍未成功。"""


def _read_env(name: str, fallback: str | None = None) -> str:
    value = os.environ.get(name, "").strip()
    if not value and fallback is not None:
        value = os.environ.get(fallback, "").strip()
    if not value.strip():
        raise LLMConfigError(f"缺少环境变量 {name}")
    return value


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    transport: httpx.BaseTransport | None,
    *,
    op: str = "chat",
    model: str = "",
) -> dict[str, Any]:
    """发一次 POST。网络层异常最多重试 1 次，其余失败立刻抛 LLMResponseError。"""
    last_error: Exception | None = None
    for retry in range(_MAX_ATTEMPTS):
        started = time.perf_counter()
        try:
            with httpx.Client(transport=transport, timeout=_TIMEOUT_SECONDS) as client:
                response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.TransportError as exc:
            last_error = exc
            observe_llm(model, False, time.perf_counter() - started)
            log_event("llm", "llm_call", level="ERROR", op=op, model=model,
                      elapsed_ms=int((time.perf_counter() - started) * 1000),
                      retry=retry, http_status=None, ok=False)
            continue
        except httpx.HTTPStatusError as exc:
            observe_llm(model, False, time.perf_counter() - started)
            log_event("llm", "llm_call", level="ERROR", op=op, model=model,
                      elapsed_ms=int((time.perf_counter() - started) * 1000),
                      retry=retry, http_status=exc.response.status_code, ok=False)
            raise LLMResponseError(f"模型接口返回 HTTP {exc.response.status_code}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            observe_llm(model, False, time.perf_counter() - started)
            log_event("llm", "llm_call", level="ERROR", op=op, model=model,
                      elapsed_ms=int((time.perf_counter() - started) * 1000),
                      retry=retry, http_status=response.status_code, ok=False)
            raise LLMResponseError("模型接口返回的不是合法 JSON") from exc
        if not isinstance(data, dict):
            observe_llm(model, False, time.perf_counter() - started)
            log_event("llm", "llm_call", level="ERROR", op=op, model=model,
                      elapsed_ms=int((time.perf_counter() - started) * 1000),
                      retry=retry, http_status=response.status_code, ok=False)
            raise LLMResponseError("模型接口返回的不是 JSON 对象")
        elapsed = time.perf_counter() - started
        observe_llm(model, True, elapsed)
        log_event("llm", "llm_call", op=op, model=model,
                  elapsed_ms=int(elapsed * 1000),
                  retry=retry, http_status=response.status_code, ok=True)
        return data
    raise LLMResponseError(
        f"模型接口请求失败：网络层重试 {_MAX_ATTEMPTS - 1} 次后仍未成功"
    ) from last_error


def _extract_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMResponseError("响应缺少非空的 choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise LLMResponseError("choices[0] 不是对象")
    message = first.get("message")
    if not isinstance(message, dict) or "content" not in message:
        raise LLMResponseError("响应缺少 choices[0].message.content")
    content = message["content"]
    if not isinstance(content, str) or not content.strip():
        raise LLMResponseError("choices[0].message.content 不是非空字符串")
    return content


def _extract_embeddings(data: dict[str, Any], expected: int) -> list[list[float]]:
    rows = data.get("data")
    if not isinstance(rows, list) or len(rows) != expected:
        raise LLMResponseError(f"响应 data 的条数与入参不一致，期望 {expected} 条")
    vectors: list[list[float]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or "embedding" not in row:
            raise LLMResponseError(f"data[{index}] 缺少 embedding")
        embedding = row["embedding"]
        if not isinstance(embedding, (list, tuple)) or not embedding:
            raise LLMResponseError(f"data[{index}].embedding 不是非空向量")
        vector: list[float] = []
        for value in embedding:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise LLMResponseError(f"data[{index}].embedding 含非数值")
            vector.append(float(value))
        vectors.append(vector)
    return vectors


def chat(
    messages: Sequence[dict[str, Any]],
    temperature: float = DEFAULT_TEMPERATURE,
    *,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """调用兼容接口取一段文本。只返回 choices[0].message.content。"""
    base_url = _read_env("LLM_BASE_URL").rstrip("/")
    api_key = _read_env("LLM_API_KEY")
    model = _read_env("LLM_MODEL")
    payload = {"model": model, "messages": list(messages), "temperature": temperature}
    headers = {"Authorization": f"Bearer {api_key}"}
    data = _post_json(f"{base_url}/chat/completions", headers, payload, transport, op="chat", model=model)
    return _extract_content(data)


def _extract_tool_chat(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMResponseError("响应缺少非空的 choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise LLMResponseError("choices[0] 不是对象")
    message = first.get("message")
    if not isinstance(message, dict):
        raise LLMResponseError("响应缺少 choices[0].message")

    content = message.get("content")
    if content is None:
        content = ""
    elif not isinstance(content, str):
        raise LLMResponseError("choices[0].message.content 不是字符串")

    finish_reason = first.get("finish_reason")
    if not isinstance(finish_reason, str):
        raise LLMResponseError("choices[0].finish_reason 不是字符串")

    raw_calls = message.get("tool_calls")
    if raw_calls is None:
        raw_calls = []
    if not isinstance(raw_calls, list):
        raise LLMResponseError("choices[0].message.tool_calls 不是数组")

    tool_calls: list[dict[str, Any]] = []
    for index, call in enumerate(raw_calls):
        if not isinstance(call, dict):
            raise LLMResponseError(f"tool_calls[{index}] 不是对象")
        call_id = call.get("id")
        function = call.get("function")
        if not isinstance(call_id, str):
            raise LLMResponseError(f"tool_calls[{index}].id 不是字符串")
        if not isinstance(function, dict):
            raise LLMResponseError(f"tool_calls[{index}].function 不是对象")
        name = function.get("name")
        if not isinstance(name, str):
            raise LLMResponseError(f"tool_calls[{index}].function.name 不是字符串")
        arguments_text = function.get("arguments")
        if not isinstance(arguments_text, str):
            raise LLMResponseError(f"tool_calls[{index}].arguments 不是字符串")
        try:
            arguments = json.loads(arguments_text)
        except (TypeError, ValueError) as exc:
            raise LLMResponseError(f"tool_calls[{index}].arguments 不是合法 JSON") from exc
        if not isinstance(arguments, dict):
            raise LLMResponseError(f"tool_calls[{index}].arguments 不是 JSON 对象")
        tool_calls.append({"id": call_id, "name": name, "arguments": arguments})

    return {"content": content, "tool_calls": tool_calls, "finish_reason": finish_reason}


def chat_with_tools(
    messages: Sequence[dict[str, Any]],
    tools: Sequence[dict[str, Any]],
    *,
    tool_choice: str | dict[str, Any] = "auto",
    temperature: float = DEFAULT_TEMPERATURE,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """调用 OpenAI 兼容的工具接口，并解析首个 choice 的工具调用。"""
    items = list(tools)
    if not items:
        raise ValueError("tools 不能为空")
    base_url = _read_env("LLM_BASE_URL").rstrip("/")
    api_key = _read_env("LLM_API_KEY")
    model = _read_env("LLM_MODEL")
    payload = {
        "model": model,
        "messages": list(messages),
        "temperature": temperature,
        "tools": items,
        "tool_choice": tool_choice,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    data = _post_json(f"{base_url}/chat/completions", headers, payload, transport, op="chat", model=model)
    return _extract_tool_chat(data)


def embed(
    texts: Sequence[str],
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[list[float]]:
    """调用兼容接口取向量。按入参顺序返回等长的二维浮点列表。"""
    base_url = _read_env("EMBEDDING_BASE_URL", "LLM_BASE_URL").rstrip("/")
    api_key = _read_env("EMBEDDING_API_KEY", "LLM_API_KEY")
    model = _read_env("EMBEDDING_MODEL")
    items = list(texts)
    if not items:
        raise LLMResponseError("embed() 的文本列表不能为空")
    payload = {"model": model, "input": items}
    headers = {"Authorization": f"Bearer {api_key}"}
    data = _post_json(f"{base_url}/embeddings", headers, payload, transport, op="embed", model=model)
    return _extract_embeddings(data, len(items))


def rerank(
    query: str,
    documents: Sequence[str],
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[int]:
    """调用 Cohere 风格重排端点，返回按 relevance_score 降序排列的文档下标。"""
    base_url = _read_env("RERANK_BASE_URL").rstrip("/")
    api_key = _read_env("RERANK_API_KEY")
    model = _read_env("RERANK_MODEL")
    items = list(documents)
    if not items:
        raise LLMResponseError("rerank() 的 documents 列表不能为空")
    payload = {"model": model, "query": query, "documents": items}
    headers = {"Authorization": f"Bearer {api_key}"}
    data = _post_json(f"{base_url}/rerank", headers, payload, transport, op="rerank", model=model)
    rows = data.get("results")
    if not isinstance(rows, list) or len(rows) != len(items):
        raise LLMResponseError("响应 results 必须完整覆盖所有候选文档")
    ranked: list[tuple[int, float]] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise LLMResponseError("results 项必须是对象")
        index = row.get("index")
        score = row.get("relevance_score")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(items):
            raise LLMResponseError("results 含越界或非法 index")
        if index in seen:
            raise LLMResponseError("results 含重复 index")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise LLMResponseError("results 含非法 relevance_score")
        seen.add(index)
        ranked.append((index, float(score)))
    if seen != set(range(len(items))):
        raise LLMResponseError("results 未覆盖全部候选文档")
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [index for index, _score in ranked]
