"""测试默认不继承开发者 shell 中的模型密钥。"""

import pytest
from contextlib import contextmanager
import shutil
import tempfile


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "anonymous: 该用例要测匿名访问，不注入默认身份"
    )


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


@pytest.fixture(autouse=True)
def isolate_logging(monkeypatch):
    """测试默认不写日志文件；日志专测会显式开启并指定临时目录。"""
    monkeypatch.setenv("LOG_DISABLED", "1")


@pytest.fixture(autouse=True)
def isolate_chroma():
    """Keep tests on a disposable Chroma directory, never the production collection."""
    import chromadb
    from backend.app.retrieve import parent_child

    path = tempfile.mkdtemp(prefix="paper-review-chroma-test-")
    client = chromadb.PersistentClient(path=path)
    parent_child.set_client_for_tests(client)
    try:
        yield
    finally:
        parent_child.reset_client_for_tests()
        client.close()
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(autouse=True)
def inject_default_identity(monkeypatch, request):
    if request.node.get_closest_marker("anonymous"):
        yield
        return

    from backend.app.auth import deps as auth_deps
    from backend.app.auth.permissions import DEFAULT_PERMISSIONS

    real = auth_deps._resolve

    def _resolve(authorization):
        if authorization:
            return real(authorization)
        return {
            "user_id": "test-default-user",
            "username": "tester",
            "role": "teacher",
            "permissions": list(DEFAULT_PERMISSIONS["teacher"]),
        }

    # 这不是放宽生产逻辑，而是补上测试缺的登录步骤；生产代码里已无任何“缺 token 就放行”分支（P1 已删）。
    monkeypatch.setattr(auth_deps, "_resolve", _resolve)
    yield
