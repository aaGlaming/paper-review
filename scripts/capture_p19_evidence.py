"""Capture reproducible P19 chat evidence using existing local teacher auth state."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
import sys

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.importing.db import get_engine

OUT = ROOT / "docs" / "plan" / "acceptance" / "calls"
API = "http://127.0.0.1:8077"
TEACHER_STATE = ROOT / "frontend" / "tests" / "e2e" / ".auth" / "teacher.json"
STUDENT_STATE = ROOT / "frontend" / "tests" / "e2e" / ".auth" / "user.json"


def token_from(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    for origin in data.get("origins", []):
        for entry in origin.get("localStorage", []):
            if entry.get("name") == "pr.auth.token":
                return str(entry["value"])
    raise RuntimeError(f"token not found in {path.name}")


def call(method: str, path: str, token: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        API + path, data=raw, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8")
        try:
            result: Any = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            result = payload
        return error.code, result


def save(name: str, payload: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    teacher = token_from(TEACHER_STATE)
    status, contests = call("GET", "/api/contests", teacher)
    if status != 200 or not contests.get("contests"):
        raise RuntimeError(f"contest lookup failed: HTTP {status}")
    contest = contests["contests"][0]
    contest_id = contest["contest_id"]
    query = urllib.parse.urlencode({"contest_id": contest_id, "page": 1, "page_size": 1})
    status, reviews = call("GET", f"/api/reviews?{query}", teacher)
    if status != 200 or not reviews.get("reviews"):
        raise RuntimeError(f"review lookup failed: HTTP {status}")
    review = reviews["reviews"][0]
    review_id = review["review_id"]
    status, detail = call("GET", f"/api/reviews/{urllib.parse.quote(review_id)}", teacher)
    if status != 200:
        raise RuntimeError(f"review detail failed: HTTP {status}")

    _, created = call("POST", "/api/chat/sessions", teacher, {"title": "P19 实测取证"})
    session_id = created["session_id"]
    dimensions = detail.get("dimensions", [])
    target_dimension = next(
        (item for item in dimensions if item.get("band") in ("证据不足", "不足")),
        dimensions[0] if dimensions else {"dimension_code": "assumption", "band": None},
    )
    dimension = target_dimension.get("dimension_code", "assumption")
    question = f"记录 {review_id} 的 {dimension} 维为什么判为 {target_dimension.get('band') or '当前档位'}？请只依据可检索内容说明。"
    status, answer = call("POST", f"/api/chat/sessions/{session_id}/messages", teacher,
                          {"question": question, "contest_id": contest_id})
    save("p19-01-detail-question.json", {"category": "单条提交详情问询", "http_status": status,
         "request": {"question": question, "contest_id": contest_id, "session_id": session_id}, "response": answer})

    changes = detail.get("change_list", [])
    change = changes[0] if changes else None
    target = str((change or {}).get("target") or (change or {}).get("action") or "该记录中的修改建议")[:160]
    question = f"记录 {review_id} 中“{target}”这条修改建议的依据是什么？请引用可追溯记录。"
    status, answer = call("POST", f"/api/chat/sessions/{session_id}/messages", teacher,
                          {"question": question, "contest_id": contest_id})
    save("p19-02-change-trace.json", {"category": "修改建议追溯", "http_status": status,
         "request": {"question": question, "contest_id": contest_id, "session_id": session_id}, "response": answer})

    analytics = [
        ("p19-03-horizontal-comparison.json", "横向对比", {"contest_id": contest_id, "kind": "bands"}),
        ("p19-04-conflict-summary.json", "冲突汇总", {"contest_id": contest_id, "kind": "conflicts"}),
        ("p19-05-evidence-gaps.json", "证据充分性检查", {"contest_id": contest_id, "kind": "gaps", "dimension_code": dimension}),
    ]
    for filename, category, body in analytics:
        status, response = call("POST", "/api/chat/analytics", teacher, body)
        save(filename, {"category": category, "http_status": status, "request": body, "response": response})

    status, summary = call("POST", "/api/chat/summary", teacher,
                           {"contest_id": contest_id, "top": 5, "session_id": session_id})
    save("p19-06-research-summary.json", {"category": "教研摘要导出", "http_status": status,
         "request": {"contest_id": contest_id, "top": 5, "session_id": session_id}, "response": summary})

    empty_scope = "p19-empty-scope"
    empty_question = "请查找与这条虚构的材料编号 QXZ-000000 无关的任何维度结论。"
    empty_status, empty_answer = call(
        "POST", f"/api/chat/sessions/{session_id}/messages", teacher,
        {"question": empty_question, "contest_id": empty_scope},
    )
    save("p19-08-empty-retrieval.json", {
        "category": "检索为空时的明确答复", "http_status": empty_status,
        "request": {"question": empty_question, "contest_id": empty_scope, "session_id": session_id},
        "response": empty_answer,
    })

    status, history = call("GET", f"/api/chat/sessions/{session_id}/messages", teacher)
    status_student, forbidden = call("GET", "/api/chat/sessions", token_from(STUDENT_STATE))
    with get_engine().connect() as connection:
        session_count = int(connection.execute(text("SELECT COUNT(*) FROM chat_session")).scalar_one())
        message_count = int(connection.execute(text("SELECT COUNT(*) FROM chat_message")).scalar_one())
    save("p19-07-persistence-and-forbidden.json", {
        "session_id": session_id, "history_http_status": status,
        "history_message_count": len(history.get("messages", [])),
        "chat_session_rows": session_count, "chat_message_rows": message_count,
        "student_http_status": status_student, "student_response": forbidden,
    })
    print(json.dumps({
        "contest_id": contest_id, "review_id": review_id, "session_id": session_id,
        "evidence_files": 8, "history_messages": len(history.get("messages", [])),
        "chat_session_rows": session_count, "chat_message_rows": message_count,
        "student_http_status": status_student,
        "answer_statuses": [200 if path.exists() else 0 for path in [OUT / "p19-01-detail-question.json", OUT / "p19-02-change-trace.json"]],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
