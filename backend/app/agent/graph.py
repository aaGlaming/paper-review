from __future__ import annotations

from langchain.agents import create_agent

from .chat_model import DeepSeekChatModel
from .middleware import BudgetMiddleware, TraceMiddleware
from .state import ReviewAgentState
from .tools import build_tools


def build_review_agent(ctx, *, chat_fn, system_prompt, budget=None):
    budget = dict(budget or {})
    model = DeepSeekChatModel(chat_fn=chat_fn)
    tools = build_tools(ctx)
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        state_schema=ReviewAgentState,
        middleware=[BudgetMiddleware(**budget), TraceMiddleware()],
        name="review_agent",
    )
