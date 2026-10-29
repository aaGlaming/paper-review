from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage

from .trace import append_step, digest_args, record_call


class BudgetExceeded(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class BudgetMiddleware(AgentMiddleware):
    def __init__(self, *, max_model_calls=12, max_tool_calls=24,
                 max_steps_per_dimension=3, wall_clock_seconds=150):
        self.max_model_calls = int(max_model_calls)
        self.max_tool_calls = int(max_tool_calls)
        self.max_steps_per_dimension = int(max_steps_per_dimension)
        self.wall_clock_seconds = float(wall_clock_seconds)
        self.model_calls = 0
        self.tool_calls = 0
        self.dimension_steps: dict[str, int] = {}
        self.started_at = time.monotonic()
        self._parent_ids: set[str] = set()
        self._submitted_codes: set[str] = set()
        self._progress_snapshot = (0, 0)
        self.no_progress_streak = 0

    def _check_clock(self) -> None:
        if time.monotonic() - self.started_at >= self.wall_clock_seconds:
            raise BudgetExceeded("wall_clock")

    def before_model(self, state, runtime):
        self._check_clock()
        self.model_calls += 1
        if self.model_calls > self.max_model_calls:
            raise BudgetExceeded("model_calls")
        return None

    def wrap_tool_call(self, request, handler):
        self._check_clock()
        self.tool_calls += 1
        if self.tool_calls > self.max_tool_calls:
            raise BudgetExceeded("tool_calls")
        tool_call = getattr(request, "tool_call", {}) or {}
        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else {}
        if isinstance(args, dict):
            code = args.get("dimension_code")
            if code:
                self.dimension_steps[str(code)] = self.dimension_steps.get(str(code), 0) + 1
                if self.dimension_steps[str(code)] > self.max_steps_per_dimension:
                    raise BudgetExceeded("dimension_steps")
        started = time.perf_counter()
        try:
            response = handler(request)
            name = str(tool_call.get("name", ""))
            if name in {"search_evidence", "submit_dimension"}:
                self._update_progress(name, response)
            return response
        finally:
            elapsed = int((time.perf_counter() - started) * 1000)
            state = getattr(request, "state", {}) or {}
            if isinstance(state, dict):
                state.setdefault("_tool_elapsed_ms", {})[str(tool_call.get("id", ""))] = elapsed

    def _update_progress(self, name: str, response: Any) -> None:
        parsed = _tool_result(response)
        if not isinstance(parsed, dict) or "ok" not in parsed:
            return
        data = parsed.get("data") if isinstance(parsed, dict) else None
        before = (len(self._parent_ids), len(self._submitted_codes))
        if name == "search_evidence" and isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("parent_id"):
                    self._parent_ids.add(str(item["parent_id"]))
        elif name == "submit_dimension" and isinstance(data, dict):
            code = data.get("dimension_code")
            if code:
                self._submitted_codes.add(str(code))
        after = (len(self._parent_ids), len(self._submitted_codes))
        if after[0] == before[0] and after[1] == before[1]:
            self.no_progress_streak += 1
        else:
            self.no_progress_streak = 0
        self._progress_snapshot = after
        if self.no_progress_streak >= 2:
            raise BudgetExceeded("no_progress")

    def after_agent(self, state, runtime):
        return {"terminated_by": state.get("terminated_by", "")}


def _tool_result(message: Any) -> dict[str, Any]:
    content = getattr(message, "content", message)
    try:
        parsed = json.loads(content) if isinstance(content, str) else content
    except (TypeError, ValueError):
        parsed = {"ok": True, "data": []}
    if not isinstance(parsed, dict):
        parsed = {"ok": True, "data": []}
    return parsed


class TraceMiddleware(AgentMiddleware):
    def __init__(self, *, recorder: Callable[..., Any] | None = None):
        self._custom_recorder = recorder is not None
        self.recorder = recorder or record_call
        self._model_started: dict[str, float] = {}
        self._write_lock = threading.Lock()

    def _record(self, state: dict[str, Any], action: str, args: dict[str, Any], result: dict[str, Any], elapsed_ms: int, node: str) -> None:
        with self._write_lock:
            self.recorder(
                review_id=str(state.get("review_id", "")),
                action=action,
                args=args,
                result=result,
                elapsed_ms=elapsed_ms,
                node=node,
            )

    def _record_model(self, state: dict[str, Any], action: str, note: str, elapsed_ms: int) -> None:
        if not self._custom_recorder:
            with self._write_lock:
                append_step(
                    review_id=str(state.get("review_id", "")),
                    node="model",
                    action=action,
                    args_digest=digest_args({}),
                    result_note=note[:256],
                    ok=True,
                    elapsed_ms=elapsed_ms,
                )
        else:
            self._record(
                state,
                action,
                {},
                {"ok": True, "data": [], "message": note, "error_code": None},
                elapsed_ms,
                "model",
            )

    def before_model(self, state, runtime):
        self._model_started[str(state.get("review_id", ""))] = time.perf_counter()
        return None

    def after_model(self, state, runtime):
        messages = state.get("messages") or []
        if not messages or not isinstance(messages[-1], AIMessage):
            return None
        message = messages[-1]
        elapsed = int((time.perf_counter() - self._model_started.pop(str(state.get("review_id", "")), time.perf_counter())) * 1000)
        if message.tool_calls:
            action = str(message.tool_calls[0].get("name", ""))
            self._record_model(state, action, f"决定调用 {len(message.tool_calls)} 个工具", elapsed)
        else:
            content = str(message.content or "")[:80]
            self._record_model(state, "final", content, elapsed)
        return None

    def wrap_tool_call(self, request, handler):
        started = time.perf_counter()
        state = getattr(request, "state", {}) or {}
        tool_call = getattr(request, "tool_call", {}) or {}
        action = str(tool_call.get("name", ""))
        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else {}
        try:
            response = handler(request)
        except Exception:
            elapsed = int((time.perf_counter() - started) * 1000)
            self._record(state, action, args if isinstance(args, dict) else {}, {"ok": False, "data": None, "error_code": "not_allowed", "message": "tool exception"}, elapsed, "tools")
            raise
        elapsed = int((time.perf_counter() - started) * 1000)
        result = _tool_result(response)
        result["ok"] = bool(result.get("ok")) and result.get("error_code") is None
        self._record(state, action, args if isinstance(args, dict) else {}, result, elapsed, "tools")
        return response
