"""Capture the two P19 deterministic record-answer checks."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.capture_p19_evidence import TEACHER_STATE, save, token_from
from backend.app.api.app import create_app
from fastapi.testclient import TestClient


def main() -> None:
    review_id = "c50ee35713d6446d835b50d30caf9e5c"
    teacher = token_from(TEACHER_STATE)
    headers = {"Authorization": f"Bearer {teacher}"}
    with TestClient(create_app()) as client:
        detail_response = client.get(f"/api/reviews/{review_id}", headers=headers)
        if detail_response.status_code != 200:
            raise RuntimeError(f"review detail failed: HTTP {detail_response.status_code}")
        contest_id = str(detail_response.json().get("contest_id") or "")
        created_response = client.post("/api/chat/sessions", headers=headers,
                                       json={"title": "P19 定点问询复检"})
        created_response.raise_for_status()
        session_id = created_response.json()["session_id"]
        questions = [
        (
            "p19-09-direct-dimension.json",
            f"记录 {review_id} 的 constraint_check 维为什么判为 证据不足？请只依据可检索内容说明。",
        ),
        (
            "p19-10-direct-change.json",
            f"记录 {review_id} 中\"节龙身把手在\"这条修改建议的依据是什么？请引用可追溯记录。",
        ),
        ]
        for filename, question in questions:
            response = client.post(
                f"/api/chat/sessions/{session_id}/messages", headers=headers,
                json={"question": question, "contest_id": contest_id},
            )
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            save(filename, {
                "category": "P19 定点记录问询复检",
                "http_status": response.status_code,
                "request": {"question": question, "contest_id": contest_id, "session_id": session_id},
                "response": payload,
            })
            print(filename, response.status_code,
                  payload.get("refs", []) if isinstance(payload, dict) else payload)


if __name__ == "__main__":
    main()
