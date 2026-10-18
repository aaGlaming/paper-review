"""测试默认不继承开发者 shell 中的模型密钥。"""

import pytest


_MODEL_ENV_KEYS = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_MODEL",
    "RERANK_BASE_URL",
    "RERANK_API_KEY",
    "RERANK_MODEL",
)


@pytest.fixture(autouse=True)
def isolate_model_configuration(monkeypatch):
    for key in _MODEL_ENV_KEYS:
        monkeypatch.setenv(key, "")
