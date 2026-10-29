"""LangChain chat model adapter backed by the project's shared model client."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import ConfigDict, Field


def _schema_parameters(schema: Any) -> dict[str, Any]:
    if schema is None:
        return {"type": "object", "properties": {}}
    if isinstance(schema, Mapping):
        return dict(schema)
    model_json_schema = getattr(schema, "model_json_schema", None)
    if callable(model_json_schema):
        return model_json_schema()
    return {"type": "object", "properties": {}}


def _normalize_tool(tool: Any) -> dict[str, Any]:
    if isinstance(tool, Mapping):
        value = dict(tool)
        function = value.get("function", value)
        if not isinstance(function, Mapping):
            raise TypeError("tool dictionary must contain a function object")
        name = function.get("name")
        description = function.get("description", "") or ""
        parameters = function.get("parameters")
        if not isinstance(name, str) or not name:
            raise ValueError("tool schema requires a function name")
        if not isinstance(parameters, Mapping):
            parameters = {"type": "object", "properties": {}}
    elif isinstance(tool, BaseTool) or (
        hasattr(tool, "name") and hasattr(tool, "args_schema")
    ):
        name = tool.name
        description = getattr(tool, "description", "") or ""
        parameters = _schema_parameters(getattr(tool, "args_schema", None))
    elif callable(tool):
        from langchain_core.utils.function_calling import convert_to_openai_tool

        converted = convert_to_openai_tool(tool)
        function = converted["function"]
        name = function["name"]
        description = function.get("description", "") or ""
        parameters = function.get("parameters") or {"type": "object", "properties": {}}
    else:
        raise TypeError("tools must be BaseTool, callable, or dictionary values")

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": dict(parameters),
        },
    }


class DeepSeekChatModel(BaseChatModel):
    """Adapt LangChain chat messages to the project's OpenAI-compatible client."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_name: str = ""
    temperature: float = 0.2
    chat_fn: Callable[..., Any] | None = Field(default=None, exclude=True)
    bound_tools: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "deepseek-compatible"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> DeepSeekChatModel:
        normalized = [_normalize_tool(tool) for tool in tools]
        return self.model_copy(update={"bound_tools": normalized})

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        converted: list[dict[str, Any]] = []
        for message in messages:
            if isinstance(message, SystemMessage):
                converted.append({"role": "system", "content": message.content})
            elif isinstance(message, HumanMessage):
                converted.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                item: dict[str, Any] = {"role": "assistant", "content": message.content}
                if message.tool_calls:
                    item["tool_calls"] = [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(call["args"], ensure_ascii=False),
                            },
                        }
                        for call in message.tool_calls
                    ]
                converted.append(item)
            elif isinstance(message, ToolMessage):
                converted.append(
                    {
                        "role": "tool",
                        "content": message.content,
                        "tool_call_id": message.tool_call_id,
                    }
                )
            else:
                raise TypeError(f"unsupported message type: {type(message).__name__}")

        chat_fn = self.chat_fn
        if chat_fn is None:
            from backend.app.llm.client import chat_with_tools

            chat_fn = chat_with_tools

        response = chat_fn(
            converted,
            tools=self.bound_tools,
            temperature=self.temperature,
        )
        tool_calls = [
            {
                "name": call["name"],
                "args": call["arguments"],
                "id": call["id"],
            }
            for call in response.get("tool_calls", [])
        ]
        message = AIMessage(
            content=response.get("content", ""),
            tool_calls=tool_calls,
            response_metadata={"finish_reason": response.get("finish_reason")},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])
