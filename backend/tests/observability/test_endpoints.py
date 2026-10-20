from fastapi.testclient import TestClient

from backend.app.api.app import create_app


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement):
        return statement


class _Engine:
    def connect(self):
        return _Connection()


class _Collection:
    def count(self):
        return 2522


def _ready_mocks(monkeypatch):
    import backend.app.importing.db as db
    import backend.app.retrieve.parent_child as parent_child

    monkeypatch.setattr(db, "get_engine", lambda: _Engine())
    monkeypatch.setattr(parent_child, "get_collection", lambda: _Collection())


def test_health_is_process_only(monkeypatch):
    monkeypatch.setenv("MYSQL_DSN", "invalid://must-not-be-read")
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["uptime_s"], int)
    assert body["version"] == "0.3.0"


def test_readyz_all_dependencies_ready(monkeypatch):
    _ready_mocks(monkeypatch)
    response = TestClient(create_app()).get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["mysql"]["ok"] is True
    assert body["checks"]["chroma"]["ok"] is True
    assert body["collection"]["count"] == 2522


def test_readyz_reports_only_chroma_failure(monkeypatch):
    _ready_mocks(monkeypatch)
    import backend.app.retrieve.parent_child as parent_child
    monkeypatch.setattr(parent_child, "get_collection", lambda: (_ for _ in ()).throw(RuntimeError("chroma down")))
    response = TestClient(create_app()).get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["failing"] == ["chroma"]
    assert body["checks"]["mysql"]["ok"] is True
    assert body["checks"]["chroma"]["ok"] is False


def test_readyz_reports_both_failures(monkeypatch):
    import backend.app.importing.db as db
    import backend.app.retrieve.parent_child as parent_child
    monkeypatch.setattr(db, "get_engine", lambda: (_ for _ in ()).throw(RuntimeError("mysql down")))
    monkeypatch.setattr(parent_child, "get_collection", lambda: (_ for _ in ()).throw(RuntimeError("chroma down")))
    response = TestClient(create_app()).get("/readyz")
    assert response.status_code == 503
    assert set(response.json()["failing"]) == {"mysql", "chroma"}


def test_metrics_content_type_and_text():
    response = TestClient(create_app()).get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert "paper_review_auth_total" in response.text
