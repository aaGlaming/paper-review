"""FastAPI 应用。

本版只装赛题目录的路由。建表不在这里做：`backend.app.importing.db.create_schema()`
按模型建表（alembic 不在锁定依赖内），应用启动不隐式改库。
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from .routes import router


MODEL_REQUIRED_ENV = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "EMBEDDING_MODEL")


def model_available() -> bool:
    """四个必需模型配置齐全时启用模型路径；嵌入端点与重排配置可独立缺省。"""
    return all(os.environ.get(name, "").strip() for name in MODEL_REQUIRED_ENV)


def create_app() -> FastAPI:
    app = FastAPI(title="paper-review 预审接口", version="0.3.0")
    app.include_router(router)
    return app


app = create_app()
