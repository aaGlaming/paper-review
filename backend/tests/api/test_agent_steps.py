from fastapi.testclient import TestClient

from backend.app.api.app import app
from backend.app.api import routes


def test_agent_steps_endpoint_returns_sorted_records(monkeypatch):
    monkeypatch.setattr(routes.trace, "load_steps", lambda review_id, session=None: [
        {"idx": 2, "action": "b"}, {"idx": 1, "action": "a"}
    ])
    response = TestClient(app).get("/api/reviews/r1/agent-steps")
    assert response.status_code == 200
    assert response.json() == {"review_id": "r1", "steps": [{"idx": 1, "action": "a"}, {"idx": 2, "action": "b"}]}


def test_agent_steps_endpoint_returns_empty_for_no_records(monkeypatch):
    monkeypatch.setattr(routes.trace, "load_steps", lambda review_id, session=None: [])
    response = TestClient(app).get("/api/reviews/missing/agent-steps")
    assert response.status_code == 200
    assert response.json() == {"review_id": "missing", "steps": []}
