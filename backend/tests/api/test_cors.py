from fastapi.testclient import TestClient

from backend.app.api.app import create_app


def _client(monkeypatch) -> TestClient:
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    return TestClient(create_app())


def test_allowed_origin_is_reflected(monkeypatch):
    response = _client(monkeypatch).get(
        "/health", headers={"Origin": "http://127.0.0.1:5173"}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_unknown_origin_gets_no_allow_origin_header(monkeypatch):
    response = _client(monkeypatch).get(
        "/health", headers={"Origin": "http://evil.example"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert response.headers.get("access-control-allow-origin") != "*"


def test_preflight_allows_configured_origin_and_method(monkeypatch):
    response = _client(monkeypatch).options(
        "/api/reviews",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert 200 <= response.status_code < 300
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
