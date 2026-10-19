import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from backend.app.agent.chat_model import DeepSeekChatModel
from backend.app.llm.client import LLMResponseError


def add_numbers(left: int, right: int) -> int:
    """Add two integers."""
    return left + right


def lookup(topic: str) -> str:
    """Look up a topic."""
    return topic


def test_bind_tools_converts_tool_shapes_and_returns_a_copy():
    structured = StructuredTool.from_function(lookup)
    raw_schema = {
        "name": "raw_lookup",
        "description": "Look up a raw topic.",
        "parameters": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    }
    model = DeepSeekChatModel()

    bound = model.bind_tools([structured, add_numbers, raw_schema])

    assert bound is not model
    assert model.bound_tools == []
    assert len(bound.bound_tools) == 3
    for tool in bound.bound_tools:
        assert tool["type"] == "function"
        assert set(tool["function"]) == {"name", "description", "parameters"}
    assert bound.bound_tools[0]["function"]["name"] == "lookup"
    assert bound.bound_tools[0]["function"]["parameters"]["properties"]["topic"]["type"] == "string"
    assert bound.bound_tools[1]["function"]["name"] == "add_numbers"
    assert set(bound.bound_tools[1]["function"]["parameters"]["properties"]) == {"left", "right"}
    assert bound.bound_tools[2]["function"]["name"] == "raw_lookup"


def test_generate_converts_tool_calls_to_langchain_ai_message():
    model = DeepSeekChatModel(
        chat_fn=lambda messages, **kwargs: {
            "content": "",
            "tool_calls": [{"id": "call-1", "name": "lookup", "arguments": {"topic": "paper"}}],
            "finish_reason": "tool_calls",
        }
    )

    result = model._generate([HumanMessage(content="find evidence")])

    message = result.generations[0].message
    assert isinstance(message, AIMessage)
    assert message.tool_calls == [{"name": "lookup", "args": {"topic": "paper"}, "id": "call-1", "type": "tool_call"}]
    assert message.response_metadata["finish_reason"] == "tool_calls"


def test_generate_converts_all_message_roles_and_keeps_tool_call_id():
    received = {}

    def fake_chat(messages, **kwargs):
        received["messages"] = messages
        return {"content": "ok", "tool_calls": [], "finish_reason": "stop"}

    model = DeepSeekChatModel(chat_fn=fake_chat)
    messages = [
        SystemMessage(content="system"),
        HumanMessage(content="human"),
        AIMessage(
            content="calling",
            tool_calls=[{"name": "lookup", "args": {"topic": "论文"}, "id": "call-2"}],
        ),
        ToolMessage(content="tool result", tool_call_id="call-2"),
    ]

    model._generate(messages)

    converted = received["messages"]
    assert [item["role"] for item in converted] == ["system", "user", "assistant", "tool"]
    assert converted[0]["content"] == "system"
    assert converted[1]["content"] == "human"
    assert converted[2]["content"] == "calling"
    assert converted[2]["tool_calls"][0] == {
        "id": "call-2",
        "type": "function",
        "function": {
            "name": "lookup",
            "arguments": json.dumps({"topic": "论文"}, ensure_ascii=False),
        },
    }
    assert converted[3] == {"role": "tool", "content": "tool result", "tool_call_id": "call-2"}


def test_generate_propagates_chat_function_exception_unchanged():
    error = LLMResponseError("model failed")

    def fail(messages, **kwargs):
        raise error

    with pytest.raises(LLMResponseError) as raised:
        DeepSeekChatModel(chat_fn=fail)._generate([HumanMessage(content="hello")])

    assert raised.value is error


def test_generate_passes_temperature_to_chat_function():
    received = {}
    model = DeepSeekChatModel(
        temperature=0.7,
        chat_fn=lambda messages, **kwargs: (
            received.update(kwargs) or {"content": "ok", "tool_calls": [], "finish_reason": "stop"}
        ),
    )

    model._generate([HumanMessage(content="hello")])

    assert received["temperature"] == 0.7
