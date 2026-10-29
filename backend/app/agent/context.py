from __future__ import annotations

from typing import Callable

from .tools import ToolContext


def build_context(*, review_id: str, contest_id: str, rubric_id: str,
                  dimensions: list[dict], constraints: list[dict],
                  retrieve_fn: Callable | None, read_parent_fn: Callable | None,
                  findings_fn: Callable | None) -> ToolContext:
    if not dimensions:
        raise ValueError("缺少 dimensions")
    if retrieve_fn is None:
        raise ValueError("缺少 retrieve_fn")
    return ToolContext(
        review_id=review_id,
        contest_id=contest_id,
        rubric_id=rubric_id,
        dimensions=dimensions,
        constraints=constraints,
        retrieve_fn=retrieve_fn,
        read_parent_fn=read_parent_fn,
        findings_fn=findings_fn,
    )
