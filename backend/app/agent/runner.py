from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError

from .graph import build_review_agent
from .middleware import BudgetExceeded
from .prompt import build_system_prompt
from .tools import BANDS, call_tool
from .trace import append_step, digest_args
from backend.app.scoring.selection import quote_is_substring
from backend.app.scoring.aggregate import weighted_sum
from .critique import critique


def _missing(ctx) -> list[str]:
    return [str(item.get("dimension_code") or "") for item in ctx.dimensions if str(item.get("dimension_code") or "") not in ctx.results]


def _decode_force(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    for value in [response.get("content"), *[c.get("arguments") for c in response.get("tool_calls") or [] if isinstance(c, dict)]]:
        if isinstance(value, str) and "```" in value:
            value = value.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(value) if isinstance(value, str) else value
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            if parsed.get("dimension_code"):
                parsed = [parsed]
            else:
                parsed = parsed.get("items", parsed.get("results", []))
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except (TypeError, ValueError):
                        parsed = []
                if isinstance(parsed, dict) and parsed.get("dimension_code"):
                    parsed = [parsed]
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return []


def _force_submit(ctx, review_id: str, chat_fn: Callable[..., Any], missing: list[str], budget: dict[str, Any] | None) -> int:
    max_calls = (budget or {}).get("max_model_calls")
    if max_calls is not None and int(max_calls) <= 1:
        return 0
    rounds = 0
    while missing and rounds < 2:
        rounds += 1
        args = {"missing": missing}
        evidence = []
        for code in missing:
            parents = list(ctx.retrieved.get(code, {}).values())
            evidence.append({"dimension_code": code, "parents": [{"parent_id": p.get("parent_id"), "chunk_ids": p.get("chunk_ids", []), "content": p.get("content", "")} for p in parents]})
        band_hint = "、".join(BANDS)
        prompt = (
            "仅完成交卷，不再检索。请为以下每个缺失维度返回 JSON 数组，"
            "每项含 dimension_code、band、quote、chunk_id。"
            f"band 只能取以下中文取值之一，不得使用英文或自创档位：{band_hint}。"
            "quote 必须逐字复制对应父块 content 的连续片段："
            + json.dumps(evidence, ensure_ascii=False)
        )
        # band 必须带 enum：空壳 schema 会让模型自创 high/medium 之类档位，
        # 导致每条提交都被 param_invalid 挡下、补交 0 条。
        item_schema = {
            "type": "object",
            "properties": {
                "dimension_code": {"type": "string"},
                "band": {"type": "string", "enum": list(BANDS)},
                "quote": {"type": "string"},
                "chunk_id": {"type": "string"},
            },
            "required": ["dimension_code", "band", "quote", "chunk_id"],
        }
        response = chat_fn(
            [{"role": "user", "content": prompt}],
            tools=[{"type": "function", "function": {
                "name": "force_submit",
                "description": "Return final dimension submissions",
                "parameters": {"type": "object", "properties": {
                    "items": {"type": "array", "items": item_schema}}}}}],
            temperature=0.2,
        )
        accepted = 0
        for item in _decode_force(response):
            code = str(item.get("dimension_code") or "")
            band = item.get("band")
            quote = item.get("quote")
            chunk_id = str(item.get("chunk_id") or "")
            parents = list(ctx.retrieved.get(code, {}).values())
            if code not in missing or band not in BANDS or not isinstance(quote, str) or not quote or not chunk_id:
                continue
            if not quote_is_substring(quote, parents):
                continue
            result = call_tool(ctx, "submit_dimension", {"dimension_code": code, "band": band, "chunk_id": chunk_id, "quote": quote})
            if result.get("ok"):
                accepted += 1
        try:
            append_step(review_id=review_id, node="model", action="force_submit", args_digest=digest_args(args), result_note=f"补交 {accepted} 条"[:256], ok=True, elapsed_ms=0)
        except Exception:
            pass
        missing = _missing(ctx)
        if not accepted:
            break
    return rounds


def make_agent_runner(*, ctx, chat_fn, budget=None) -> Callable[[dict], dict]:
    def agent_runner(state: dict) -> dict:
        graph = build_review_agent(ctx, chat_fn=chat_fn, system_prompt=build_system_prompt(ctx.dimensions, ctx.constraints), budget=budget)
        review_id = str(state.get("review_id") or ctx.review_id)
        initial = {
            "messages": [HumanMessage(content="请按系统提示完成本次论文预审并提交所有维度结论。")],
            "review_id": review_id,
            "contest_id": str(state.get("contest_id") or ctx.contest_id),
            "rubric_id": str(state.get("rubric_id") or ctx.rubric_id),
            "budget": dict(budget or {}), "dimension_results": {}, "terminated_by": "",
        }
        terminated = "budget_exhausted"
        try:
            graph.invoke(initial, config={"configurable": {"thread_id": review_id}, "recursion_limit": 45})
            terminated = "all_submitted" if not _missing(ctx) else "budget_exhausted"
        except BudgetExceeded as exc:
            terminated = "no_progress" if exc.reason == "no_progress" else "budget_exhausted"
        except GraphRecursionError:
            terminated = "recursion_limit_reached"
        missing = _missing(ctx)
        if missing:
            _force_submit(ctx, review_id, chat_fn, missing, budget)
        results = dict(ctx.results)
        for code in _missing(ctx):
            results[code] = {"band": "证据不足", "status": "证据不足", "chunk_ids": [], "quote": None, "reason": "agent 未提交"}
        if not _missing(ctx) and terminated not in {"recursion_limit_reached", "budget_exhausted", "no_progress"}:
            terminated = "all_submitted"
        critique_downgrades = 0
        try:
            reviewed, actions = critique(ctx, results, chat_fn=None)
            critique_downgrades = sum(1 for action in actions if action.get("action") == "downgrade")
            results = reviewed
            ctx.results.clear()
            ctx.results.update(reviewed)
            weighted_sum(ctx.dimensions, list(results.values()))
        except Exception as exc:
            try:
                append_step(
                    review_id=review_id,
                    node="critique",
                    action="critique_failed",
                    args_digest=digest_args({"review_id": review_id}),
                    result_note=type(exc).__name__,
                    ok=False,
                    elapsed_ms=0,
                )
            except Exception:
                pass
        try:
            append_step(
                review_id=review_id,
                node="runner",
                action="terminated",
                args_digest=digest_args({"terminated_by": terminated}),
                result_note=terminated,
                ok=terminated == "all_submitted",
                elapsed_ms=0,
            )
        except Exception:
            pass
        return {"dimension_results": results, "terminated_by": terminated, "critique_downgrades": critique_downgrades}
    return agent_runner
