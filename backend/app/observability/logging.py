"""Small dependency-free JSON logging foundation for Phase-3."""

from __future__ import annotations

import json
import logging as std_logging
import os
import re
import sys
import threading
from contextvars import ContextVar, Token
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

MODULES: tuple[str, ...] = (
    "api", "graph", "agent", "llm", "retrieve", "scoring", "review",
    "report", "importing", "auth", "ai_chat", "dashboard", "errors",
    "audit", "frontend",
)
# agent 目录本版不写日志；结构化 agent_step 是唯一轨迹口径，目录预留给 P19 AI 问询子图。
_LEVELS = {"DEBUG": std_logging.DEBUG, "INFO": std_logging.INFO,
           "WARNING": std_logging.WARNING, "ERROR": std_logging.ERROR}
_DATE_RE = re.compile(r"^(?P<module>[a-z_]+)-(?P<date>\d{8})\.log$")
_SECRET_NAMES = {"llm_api_key", "embedding_api_key", "rerank_api_key", "mysql_dsn"}
_state_lock = threading.RLock()
_configured = False
_handlers: dict[str, "JsonDailyHandler"] = {}
_max_bytes_override: int | None = None
_stderr_notified = False

# 当前请求处理链上正在评审哪篇论文。埋点不可能层层透传 review_id
# （底层 client 只认 model，selection 的调用方也拿不到），
# 所以用 ContextVar 绑一次，log_event 自动补进字段。
_review_id_ctx: ContextVar[str | None] = ContextVar("paper_review_review_id", default=None)


def bind_review_id(review_id: Any) -> Token:
    """把 review_id 绑到当前上下文；同线程 / 同任务内后续日志自动带上它。"""
    return _review_id_ctx.set(str(review_id) if review_id else None)


def unbind_review_id(token: Token) -> None:
    """解除绑定。token 必须来自同一次 bind_review_id。"""
    try:
        _review_id_ctx.reset(token)
    except (ValueError, RuntimeError):
        pass


def _root_dir() -> Path:
    raw = os.environ.get("LOG_DIR", "").strip()
    return Path(raw) if raw else Path(__file__).resolve().parents[3] / "logs"


def _disabled() -> bool:
    return os.environ.get("LOG_DISABLED", "").strip() == "1"


def _level() -> int:
    return _LEVELS.get(os.environ.get("LOG_LEVEL", "INFO").strip().upper(), std_logging.INFO)


def _safe_value(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        return str(value)


def _safe_fields(fields: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    secret_values = {
        os.environ.get(name, "")
        for name in ("LLM_API_KEY", "EMBEDDING_API_KEY", "RERANK_API_KEY", "MYSQL_DSN")
        if os.environ.get(name, "")
    }
    for key, value in fields.items():
        normalized = str(key).lower()
        if (normalized in _SECRET_NAMES or normalized.endswith("_password")
                or normalized == "password_hash" or "api_key" in normalized
                or normalized.endswith("_dsn")):
            continue
        if isinstance(value, str) and value in secret_values:
            continue
        result[str(key)] = _safe_value(value)
    return result


def _notify_failure(exc: Exception) -> None:
    global _stderr_notified
    with _state_lock:
        if _stderr_notified:
            return
        _stderr_notified = True
    try:
        print(f"paper-review logging disabled after write failure: {type(exc).__name__}", file=sys.stderr)
    except Exception:
        pass


class JsonDailyHandler(std_logging.Handler):
    def __init__(self, module: str, root: Path, *, max_bytes: int = 50 * 1024 * 1024, backup_count: int = 5):
        super().__init__()
        self.module = module
        self.root = root
        self.module_dir = root / module
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._date = ""
        self._stream = None

    def _path(self, date: str) -> Path:
        return self.module_dir / f"{self.module}-{date}.log"

    def _open_for_date(self, date: str) -> None:
        if self._stream is not None:
            self._stream.close()
        self.module_dir.mkdir(parents=True, exist_ok=True)
        self._date = date
        self._stream = self._path(date).open("a", encoding="utf-8", newline="\n")

    def _roll(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        base = self._path(self._date)
        for index in range(self.backup_count, 0, -1):
            source = Path(f"{base}.{index - 1}") if index > 1 else base
            target = Path(f"{base}.{index}")
            if target.exists():
                target.unlink()
            if source.exists():
                source.rename(target)
        self._open_for_date(self._date)

    def emit(self, record: std_logging.LogRecord) -> None:
        try:
            date = datetime.now().astimezone().strftime("%Y%m%d")
            if self._stream is None or date != self._date:
                self._open_for_date(date)
            text = self.format(record)
            encoded = (text + "\n").encode("utf-8")
            if self._stream.tell() + len(encoded) > self.max_bytes and self._stream.tell() > 0:
                self._roll()
            self._stream.write(text + "\n")
            self._stream.flush()
        except Exception as exc:
            _notify_failure(exc)

    def close(self) -> None:
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        finally:
            super().close()


class _JsonFormatter(std_logging.Formatter):
    def format(self, record: std_logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "module": record.name.removeprefix("paper_review."),
            "event": str(getattr(record, "event", "")),
        }
        payload.update(_safe_fields(dict(getattr(record, "fields", {}))))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _cleanup(root: Path) -> None:
    try:
        retain = max(0, int(os.environ.get("LOG_RETAIN_DAYS", "30")))
        cutoff = datetime.now().date() - timedelta(days=retain)
        for path in root.glob("*/*.log"):
            match = _DATE_RE.match(path.name)
            if match and datetime.strptime(match.group("date"), "%Y%m%d").date() < cutoff:
                path.unlink(missing_ok=True)
    except Exception as exc:
        _notify_failure(exc)


def setup_logging() -> None:
    global _configured
    with _state_lock:
        if _disabled():
            return
        if _configured:
            return
        root = _root_dir()
        try:
            for module in MODULES:
                (root / module).mkdir(parents=True, exist_ok=True)
            _cleanup(root)
            for module in MODULES:
                logger = std_logging.getLogger(f"paper_review.{module}")
                logger.setLevel(_level())
                logger.propagate = False
                handler = JsonDailyHandler(module, root, max_bytes=_max_bytes_override or 50 * 1024 * 1024)
                handler.setFormatter(_JsonFormatter())
                logger.addHandler(handler)
                _handlers[module] = handler
            _configured = True
        except Exception as exc:
            _notify_failure(exc)


def log_event(module: str, event: str, level: str = "INFO", **fields: Any) -> None:
    if module not in MODULES:
        raise ValueError(f"unknown log module: {module}")
    level_name = str(level).upper()
    if level_name not in _LEVELS:
        raise ValueError(f"invalid log level: {level}")
    if _disabled():
        return
    # 显式传了就用显式的；没传（或传了 None/空串）才回填上下文里的 review_id。
    # 这样 llm 这类拿不到评审上下文的底层模块也能被串进同一次预审。
    if not fields.get("review_id"):
        bound = _review_id_ctx.get()
        if bound:
            fields["review_id"] = bound
    try:
        setup_logging()
        logger = std_logging.getLogger(f"paper_review.{module}")
        if _LEVELS[level_name] < logger.getEffectiveLevel():
            return
        logger.log(_LEVELS[level_name], event, extra={"event": event, "fields": fields})
    except Exception as exc:
        _notify_failure(exc)


def reset_logging_for_tests() -> None:
    global _configured, _stderr_notified, _max_bytes_override
    with _state_lock:
        for handler in list(_handlers.values()):
            logger = std_logging.getLogger(f"paper_review.{handler.module}")
            logger.removeHandler(handler)
            handler.close()
        _handlers.clear()
        _configured = False
        _stderr_notified = False
        _max_bytes_override = None


def set_max_bytes_for_tests(value: int) -> None:
    global _max_bytes_override
    reset_logging_for_tests()
    _max_bytes_override = int(value)
