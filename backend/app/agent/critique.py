"""Post processing checks that can only lower a submitted dimension band."""

from __future__ import annotations

import json
from typing import Any, Callable

from backend.app.scoring.aggregate import BANDS
from backend.app.scoring.selection import apply_mention_guard, join_evidence, quote_is_substring

from .trace import append_step, digest_args


def _parents(ctx: Any, code: str) -> list[dict[str, Any]]:
    return list((getattr(ctx, "retrieved", {}) or {}).get(code, {}).values())


def _record(ctx: Any, action: str, args: dict[str, Any], note: str, ok: bool) -> dict[str, Any]:
    item = {"action": action, "result_note": note, "ok": ok}
    try:
        append_step(
            review_id=str(getattr(ctx, "review_id", "")),
            node="critique",
            action=action,
            args_digest=digest_args(args),
            result_note=note[:256],
            ok=ok,
            elapsed_ms=0,
        )
    except Exception:
        pass
    return item


def _response_items(response: Any) -> list[dict[str, Any]]:
    values: list[Any] = []
    if isinstance(response, dict):
        values.append(response.get("content"))
        values.extend(
            item.get("arguments")
            for item in response.get("tool_calls") or ()
            if isinstance(item, dict)
        )
    for value in values:
        if isinstance(value, str):
            text = value.strip().replace("```json", "").replace("```", "").strip()
            try:
                value = json.loads(text)
            except (TypeError, ValueError):
                continue
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def critique(
    ctx: Any,
    results: dict[str, dict[str, Any]],
    *,
    chat_fn: Callable[..., Any] | None = None,
    max_downgrades: int = 2,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Review submitted results. Every accepted change is exactly one band lower."""
    updated = {code: dict(value) for code, value in results.items()}
    actions: list[dict[str, Any]] = []
    used = 0
    dimensions = {
        str(item.get("dimension_code") or ""): item
        for item in getattr(ctx, "dimensions", ())
        if isinstance(item, dict)
    }

    for code, current in list(updated.items()):
        band = current.get("band")
        if band not in (BANDS[0], BANDS[1]):
            continue
        parents = _parents(ctx, code)
        dimension = dimensions.get(code, {})
        guard = apply_mention_guard(
            band,
            evidence_text=join_evidence(parents),
            constraints=getattr(ctx, "constraints", ()),
            dimension_section_types=dimension.get("section_types") or (),
        )
        if guard.get("downgraded"):
            if used >= max_downgrades:
                actions.append(_record(ctx, "rejected", {"dimension_code": code}, "quota_exceeded", False))
            else:
                lower = BANDS[BANDS.index(band) + 1]
                updated[code] = {**current, "band": lower, "status": lower, "guard": guard}
                used += 1
                actions.append(_record(ctx, "downgrade", {"dimension_code": code}, "mention_guard", True))
            continue
        if chat_fn is None or not parents:
            continue
        prompt = json.dumps(
            {
                "dimension_code": code,
                "constraints": list(getattr(ctx, "constraints", ()) or ()),
                "parents": [
                    {"parent_id": p.get("parent_id"), "chunk_ids": p.get("chunk_ids", []), "content": p.get("content", "")}
                    for p in parents[:4]
                ],
                "current_band": band,
                "instruction": "Only return JSON {downgrade,reason,chunk_id,quote}; downgrade may lower exactly one band.",
            },
            ensure_ascii=False,
        )
        response = chat_fn(
            [{"role": "user", "content": prompt}],
            tools=[{"type": "function", "function": {"name": "critique", "parameters": {"type": "object"}}}],
            temperature=0.0,
        )
        item = (_response_items(response) or [{}])[0]
        requested = item.get("band")
        if requested in BANDS and BANDS.index(requested) < BANDS.index(band):
            actions.append(_record(ctx, "rejected", {"dimension_code": code}, "upgrade_not_allowed", False))
            continue
        if not item.get("downgrade"):
            continue
        if used >= max_downgrades:
            actions.append(_record(ctx, "rejected", {"dimension_code": code}, "quota_exceeded", False))
            continue
        quote = item.get("quote")
        chunk_id = str(item.get("chunk_id") or "")
        valid_chunk = any(chunk_id in tuple(p.get("chunk_ids") or ()) for p in parents)
        if not isinstance(quote, str) or not quote_is_substring(quote, parents):
            actions.append(_record(ctx, "rejected", {"dimension_code": code}, "quote_not_substring", False))
            continue
        if not valid_chunk:
            actions.append(_record(ctx, "rejected", {"dimension_code": code}, "chunk_id_invalid", False))
            continue
        target = BANDS[BANDS.index(band) + 1]
        if requested is not None and requested != target:
            actions.append(_record(ctx, "rejected", {"dimension_code": code}, "downgrade_step_invalid", False))
            continue
        updated[code] = {**current, "band": target, "status": target, "quote": quote, "chunk_ids": [chunk_id]}
        used += 1
        actions.append(_record(ctx, "downgrade", {"dimension_code": code}, "model_review", True))
    return updated, actions
