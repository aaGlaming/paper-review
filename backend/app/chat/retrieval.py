"""按赛题检索评审记录片段；不生成问答内容。"""

from __future__ import annotations

from typing import Any, Callable

from ..retrieve import parent_child


def search_records(
    query: str,
    *,
    contest_id: str,
    limit: int = 8,
    retrieve_fn: Callable[..., Any] | None = None,
) -> list[dict[str, str]]:
    function = retrieve_fn or parent_child.search_children_then_parents
    kwargs: dict[str, Any] = {
        "contest_id": contest_id,
        "rubric_id": "",
        "review_id": None,
        "doc_types": ("review_record",),
        "limit": limit,
    }
    if retrieve_fn is None:
        from ..llm import client as llm_client

        kwargs["query_embedding"] = llm_client.embed([query])[0]
    parents = function(query, **kwargs)
    results = []
    for parent in parents or ():
        parent_id = str(parent.parent_id)
        parts = parent_id.rsplit("-", 1)
        if len(parts) != 2:
            continue
        results.append({
            "review_id": str(getattr(parent, "review_id", "") or parent_id[3:35]),
            "dimension_code": parts[1],
            "parent_id": parent_id,
            "content": str(parent.content),
        })
    return results
