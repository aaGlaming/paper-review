from __future__ import annotations

import time
from typing import Callable

from .tools import ToolContext, call_tool


def run_linear_probe(ctx: ToolContext, *, recorder: Callable) -> dict:
    first = ctx.dimensions[0] if ctx.dimensions else {}
    code = str(first.get("dimension_code") or "")
    name = str(first.get("name") or code)
    calls = [
        ("list_dimensions", {}),
        ("get_constraints", {}),
        ("search_evidence", {"dimension_code": code, "query": name}),
    ]
    written = 0
    first_hits = 0
    for action, args in calls:
        started = time.perf_counter()
        try:
            result = call_tool(ctx, action, args)
        except Exception:
            result = {"ok": False, "data": None, "error_code": "not_allowed", "message": "probe exception"}
        elapsed = int((time.perf_counter() - started) * 1000)
        try:
            recorder(review_id=ctx.review_id, action=action, args=args, result=result, elapsed_ms=elapsed)
            written += 1
        except Exception:
            pass
        if action == "search_evidence" and result.get("ok") and isinstance(result.get("data"), list):
            first_hits = len(result["data"])
    return {"steps": written, "first_dimension_hits": first_hits}
