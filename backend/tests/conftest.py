"""测试默认不继承开发者 shell 中的模型密钥。"""

import pytest
from contextlib import contextmanager


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


@pytest.fixture(autouse=True)
def isolate_agent_trace(monkeypatch, request):
    path = str(request.node.fspath).replace("\\", "/")
    if "/tests/agent/" not in path:
        yield
        return

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from backend.app.agent.trace import AgentTraceBase
    import backend.app.importing.db as db_mod

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AgentTraceBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    @contextmanager
    def _scope():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(db_mod, "session_scope", _scope)
    yield
