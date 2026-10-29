from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.app import create_app


def test_published_rubric_endpoint_returns_dimensions_and_four_bands(monkeypatch):
    from backend.app.api import routes

    monkeypatch.setattr(
        routes.report_rubric,
        "load_published_rubric",
        lambda _contest_id, session=None: {
            "contest_id": "contest-a",
            "rubric_id": "rubric-a-v2",
            "version": 2,
            "dimensions": [
                {
                    "dimension_code": code,
                    "name": f"维度 {code}",
                    "weight": 20,
                    "evidence_prompts": ["核对假设依据"],
                    "bands": [
                        {"band": "充分", "score": 4, "description": "描述甲"},
                        {"band": "基本", "score": 3, "description": "描述乙"},
                        {"band": "不足", "score": 2, "description": "描述丙"},
                        {"band": "证据不足", "score": None, "description": "描述丁"},
                    ],
                }
                for code in ("assumption", "modeling", "solution", "constraint_check", "presentation")
            ],
        },
        raising=False,
    )
    client = TestClient(create_app())

    response = client.get("/api/contests/contest-a/rubric")

    assert response.status_code == 200
    body = response.json()
    assert body["rubric_id"] == "rubric-a-v2"
    assert len(body["dimensions"]) == 5
    assert all(len(dimension["bands"]) == 4 for dimension in body["dimensions"])
    assert body["dimensions"][0]["bands"][0] == {
        "band": "充分", "score": 4, "description": "描述甲"
    }


def test_single_paper_endpoint_returns_gold_system_results_and_differences(monkeypatch):
    from backend.app.api import routes

    monkeypatch.setattr(routes, "_load_eval_paper", lambda _paper_id: {
        "paper_id": "eval-01",
        "contest_id": "contest-a",
        "title": "评测论文",
        "text": "## 假设\n论文正文",
        "gold": [{"dimension_code": "assumption", "band": "充分"}],
    })
    monkeypatch.setattr(routes.report_evaluation, "_load_rubric", lambda _contest_id: {
        "dimensions": [{"dimension_code": "assumption", "name": "假设", "weight": 20, "section_types": ["假设"]}],
        "constraints": [],
    }, raising=False)

    response = TestClient(create_app()).get("/api/eval/papers/eval-01")

    assert response.status_code == 200
    body = response.json()
    assert body["gold"][0] == {"dimension_code": "assumption", "band": "充分"}
    assert body["system"][0]["band"] == "基本"
    assert body["differences"] == [{
        "dimension_code": "assumption", "gold_band": "充分", "system_band": "基本", "matches": False
    }]
    assert body["source"] == "deterministic"


def test_single_paper_endpoint_explains_missing_gold_and_unknown_paper(monkeypatch):
    from backend.app.api import routes

    def load_paper(paper_id):
        if paper_id == "demo-paper":
            return {"paper_id": paper_id, "contest_id": "", "title": "演示", "text": "正文", "gold": None}
        return None

    monkeypatch.setattr(routes, "_load_eval_paper", load_paper)
    client = TestClient(create_app())

    no_gold = client.get("/api/eval/papers/demo-paper")
    unknown = client.get("/api/eval/papers/missing")

    assert no_gold.status_code == 200
    assert no_gold.json()["gold_available"] is False
    assert no_gold.json()["explanation"]
    assert no_gold.json()["differences"] is None
    assert unknown.status_code == 404
