"""FastAPI 应用。

本版只装赛题目录的路由。建表不在这里做：`backend.app.importing.db.create_schema()`
按模型建表（alembic 不在锁定依赖内），应用启动不隐式改库。
"""

from __future__ import annotations

from fastapi import FastAPI

from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="paper-review 预审接口", version="0.3.0")
    app.include_router(router)
    return app


app = create_app()
