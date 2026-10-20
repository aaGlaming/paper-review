"""FastAPI 应用。

本版只装赛题目录的路由。建表不在这里做：`backend.app.importing.db.create_schema()`
按模型建表（alembic 不在锁定依赖内），应用启动不隐式改库。
"""

from __future__ import annotations

import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from .auth_routes import router as auth_router
from .chat_routes import router as chat_router
from .reviews_list_routes import router as reviews_list_router
from .routes import router
from .user_routes import router as user_router
from ..observability import log_event, setup_logging
from ..observability.metrics import render as render_metrics


MODEL_REQUIRED_ENV = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "EMBEDDING_MODEL")
_STARTED_AT = time.monotonic()


def model_available() -> bool:
    """四个必需模型配置齐全时启用模型路径；嵌入端点与重排配置可独立缺省。"""
    return all(os.environ.get(name, "").strip() for name in MODEL_REQUIRED_ENV)


def create_app() -> FastAPI:
    app = FastAPI(title="paper-review 预审接口", version="0.3.0")

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        if request.url.path in {"/health", "/readyz", "/metrics"}:
            return await call_next(request)
        setup_logging()
        started = time.perf_counter()
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            route = request.scope.get("route")
            path = getattr(route, "path", None) or request.url.path
            review_id = request.path_params.get("review_id")
            fields = {
                "method": request.method,
                "path": path,
                "status": getattr(locals().get("response"), "status_code", 500),
                "elapsed_ms": elapsed_ms,
            }
            if review_id:
                fields["review_id"] = str(review_id)
            log_event("api", "request", **fields)

    async def unhandled_exception(request: Request, exc: Exception):
        log_event(
            "errors",
            "unhandled_exception",
            level="ERROR",
            path=getattr(request.scope.get("route"), "path", request.url.path),
            method=request.method,
            exc_type=type(exc).__name__,
            exc_message=str(exc).splitlines()[0][:500],
            review_id=request.path_params.get("review_id"),
        )
        return JSONResponse(status_code=500, content={"detail": "internal error"})

    app.add_exception_handler(Exception, unhandled_exception)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "uptime_s": int(time.monotonic() - _STARTED_AT),
            "version": app.version,
        }

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        checks: dict[str, dict[str, object]] = {}
        collection_info: dict[str, object] | None = None

        started = time.perf_counter()
        try:
            from ..importing.db import get_engine

            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            checks["mysql"] = {"ok": True, "elapsed_ms": int((time.perf_counter() - started) * 1000)}
        except Exception as exc:
            checks["mysql"] = {
                "ok": False,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "error": _safe_dependency_error(exc),
            }

        started = time.perf_counter()
        try:
            from ..retrieve.parent_child import get_collection

            collection = get_collection()
            count = int(collection.count())
            checks["chroma"] = {"ok": True, "elapsed_ms": int((time.perf_counter() - started) * 1000)}
            collection_info = {"name": "paper_review", "count": count}
        except Exception as exc:
            checks["chroma"] = {
                "ok": False,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "error": _safe_dependency_error(exc),
            }

        failing = [name for name, check in checks.items() if not check.get("ok")]
        if failing:
            body: dict[str, object] = {"status": "not_ready", "checks": checks, "failing": failing}
            return JSONResponse(status_code=503, content=body)
        return JSONResponse(status_code=200, content={"status": "ready", "checks": checks, "collection": collection_info})

    @app.get("/metrics")
    def metrics_endpoint() -> Response:
        return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")

    app.include_router(router)
    app.include_router(reviews_list_router)
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(chat_router)
    return app


def _safe_dependency_error(exc: Exception) -> str:
    message = str(exc).splitlines()[0][:500]
    dsn = os.environ.get("MYSQL_DSN", "")
    if dsn:
        message = message.replace(dsn, "[redacted]")
    return f"{type(exc).__name__}: {message}"


app = create_app()
