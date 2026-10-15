"""数据库连接。

连接串只从环境变量 `MYSQL_DSN` 读（项目根的 `.env` 会被读进环境变量，已存在的环境变量优先）。
凭据不进代码、不进测试、不进日志：本模块只传递连接串，不打印它。
建表用 `Base.metadata.create_all()`，不引入 alembic。
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"
DSN_ENV_KEY = "MYSQL_DSN"

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


def _load_env_file() -> None:
    """把项目根的 .env 读进环境变量；已经存在的环境变量不覆盖。"""
    if ENV_FILE.is_file():
        load_dotenv(ENV_FILE, override=False)


def get_dsn() -> str:
    """取连接串。缺失时抛 RuntimeError，错误信息里不带任何凭据。"""
    _load_env_file()
    dsn = os.environ.get(DSN_ENV_KEY, "").strip()
    if not dsn:
        raise RuntimeError(f"缺少环境变量 {DSN_ENV_KEY}，无法连接数据库")
    return dsn


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(get_dsn(), pool_pre_ping=True, future=True)
    return _ENGINE


def get_session_factory() -> sessionmaker[Session]:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SESSION_FACTORY


@contextmanager
def session_scope() -> Iterator[Session]:
    """用完即关的会话：成功提交，出错回滚。"""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_schema() -> None:
    """按模型建表。表已存在时是空操作。"""
    from . import models

    models.Base.metadata.create_all(get_engine())
