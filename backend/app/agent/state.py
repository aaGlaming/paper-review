from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentState


class ReviewAgentState(AgentState, total=False):
    review_id: str
    contest_id: str
    rubric_id: str
    budget: dict[str, Any]
    dimension_results: dict[str, Any]
    terminated_by: str
