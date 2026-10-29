from __future__ import annotations

from importlib import import_module

app_module = import_module("backend.app.api.app")
routes_module = import_module("backend.app.api.routes")


_REQUIRED = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "EMBEDDING_MODEL")


def test_model_available_requires_all_four_chat_model_settings(monkeypatch):
    available = getattr(app_module, "model_available", None)
    assert callable(available), "api.app must expose model_available()"
    for key in _REQUIRED:
        monkeypatch.setenv(key, "configured")
    assert available() is True

    for key in _REQUIRED:
        monkeypatch.setenv(key, "")
        assert available() is False
        monkeypatch.setenv(key, "configured")


def test_graph_module_keeps_model_transport_outside_graph():
    from pathlib import Path

    source = (Path(__file__).parents[2] / "app" / "graph" / "review_graph.py").read_text(encoding="utf-8")
    assert "HTTP" not in source
    assert "llm.client" not in source


def test_eval_requires_explicit_model_force_and_passes_chat(monkeypatch):
    from backend.app.llm import client as llm_client

    for key in _REQUIRED:
        monkeypatch.setenv(key, "configured")
    calls = []
    monkeypatch.setattr(routes_module.report_evaluation, "run_eval", lambda **kwargs: calls.append(kwargs) or {"source": "model"})

    result = routes_module.eval_summary(force="model")

    assert result == {"source": "model"}
    assert calls == [{"chat": llm_client.chat}]


def test_eval_default_remains_deterministic_even_when_model_is_configured(monkeypatch):
    for key in _REQUIRED:
        monkeypatch.setenv(key, "configured")
    calls = []
    monkeypatch.setattr(routes_module.report_evaluation, "run_eval", lambda **kwargs: calls.append(kwargs) or {"source": "deterministic"})

    assert routes_module.eval_summary() == {"source": "deterministic"}
    assert calls == [{}]
