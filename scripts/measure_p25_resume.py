"""Run exactly three live create-confirm-report measurements for P25."""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime
from pathlib import Path

import httpx


BASE_URL = "http://127.0.0.1:8077"
USERNAME = "e2e_teacher"
PASSWORD = "e2e-teacher-password-123"
PROJECT = Path(__file__).resolve().parents[1]
LLM_LOG = PROJECT / "logs" / "llm" / f"llm-{datetime.now():%Y%m%d}.log"


def llm_events(review_id: str) -> list[dict]:
    if not LLM_LOG.exists():
        return []
    events = []
    for line in LLM_LOG.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("review_id") == review_id and item.get("event") == "llm_call":
            events.append(item)
    return events


def main() -> None:
    results: list[dict] = []
    with httpx.Client(base_url=BASE_URL, timeout=150.0) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
        )
        if login.status_code != 200:
            raise RuntimeError(f"teacher login failed: HTTP {login.status_code}")
        token = login.json()["token"]
        client.headers["Authorization"] = f"Bearer {token}"

        contests_response = client.get("/api/contests")
        contests_response.raise_for_status()
        contests = contests_response.json().get("contests", [])
        contest_id = next(
            str(item.get("contest_id"))
            for item in contests
            if item.get("contest_id")
        )
        samples_response = client.get("/api/samples", params={"is_demo": "true"})
        samples_response.raise_for_status()
        samples = samples_response.json().get("samples", [])
        sample = next(
            item for item in samples if item.get("contest_id") == contest_id
        )

        for attempt in range(1, 4):
            started = time.perf_counter()
            result: dict = {"attempt": attempt, "contest_id": contest_id}
            review_id = ""
            try:
                created = client.post(
                    "/api/reviews",
                    json={"sample_id": sample["sample_id"], "contest_id": contest_id},
                )
                if created.status_code != 201:
                    result.update(
                        status=created.status_code,
                        failure=created.text[:500],
                    )
                else:
                    created_body = created.json()
                    review_id = str(created_body["review_id"])
                    resumed = client.post(
                        f"/api/reviews/{review_id}/resume",
                        json={"sections": created_body.get("sections", [])},
                    )
                    result["status"] = resumed.status_code
                    if resumed.is_success:
                        body = resumed.json()
                        dimensions = body.get("dimensions", [])
                        result["mode"] = body.get("source", body.get("mode"))
                        result["response_dimension_chat_calls"] = sum(
                            int(item.get("chat_calls", 0) or 0)
                            for item in dimensions
                        )
                    else:
                        result["failure"] = resumed.text[:500]
            except Exception as exc:  # one attempt is recorded even on transport errors
                result["status"] = None
                result["failure"] = f"{type(exc).__name__}: {exc}"
            finally:
                result["wall_ms"] = round((time.perf_counter() - started) * 1000)
                if review_id:
                    events = llm_events(review_id)
                    result["review_id"] = review_id
                    result["llm_request_count"] = len(events)
                    result["chat_calls"] = sum(
                        1 for event in events if event.get("op") == "chat"
                    )
                    result["llm_ops"] = {
                        operation: sum(1 for event in events if event.get("op") == operation)
                        for operation in sorted({str(event.get("op")) for event in events})
                    }
                    result["llm_http_statuses"] = [
                        event.get("http_status") for event in events
                    ]
                    result["model_request_sent"] = bool(events)
                else:
                    result["llm_request_count"] = 0
                    result["chat_calls"] = 0
                    result["llm_ops"] = {}
                    result["llm_http_statuses"] = []
                    result["model_request_sent"] = False
                results.append(result)
                print(json.dumps(result, ensure_ascii=False))

    successful = [item["wall_ms"] for item in results if item.get("status") == 200]
    if successful:
        print(
            json.dumps(
                {
                    "summary": "successful_resume_only",
                    "count": len(successful),
                    "median_wall_ms": statistics.median(successful),
                    "max_wall_ms": max(successful),
                },
                ensure_ascii=False,
            )
        )
    else:
        print(json.dumps({"summary": "no_successful_resume"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
