from __future__ import annotations

import json
import logging
from logging import Logger
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from contextvars import ContextVar, Token
from contextlib import contextmanager
from typing import Any, Dict, Optional
from os import getenv
import atexit


_LOG_CONTEXT: ContextVar[Dict[str, Any]] = ContextVar("tfm_log_context", default={})
_LOG_QUEUE: Queue[logging.LogRecord] = Queue(-1)
_QUEUE_LISTENER: QueueListener | None = None


class StructuredJsonFormatter(logging.Formatter):
    """Render log records as JSON with stable keys."""

    RESERVED = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "service",
        "log_context",
    }

    def format(self, record: logging.LogRecord) -> str:
        base: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        service = getattr(record, "service", None)
        if service:
            base["service"] = service

        context_payload = getattr(record, "log_context", None)
        if context_payload:
            base["context"] = context_payload

        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self.RESERVED and not key.startswith("_")
        }
        if extra:
            base["extra"] = extra

        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            base["stack"] = self.formatStack(record.stack_info)

        return json.dumps(base, default=str, ensure_ascii=False)


_CONFIGURED = False
_SERVICE_NAME: Optional[str] = None
_RECORD_FACTORY = logging.getLogRecordFactory()


def get_log_context() -> Dict[str, Any]:
    """Return a shallow copy of the current structured logging context."""

    return dict(_LOG_CONTEXT.get({}))


def bind_log_context(**values: Any) -> Token:
    """Bind additional context for the current task/thread."""

    merged = get_log_context()
    merged.update({key: value for key, value in values.items() if value is not None})
    return _LOG_CONTEXT.set(merged)


def clear_log_context(token: Token | None = None) -> None:
    if token is not None:
        _LOG_CONTEXT.reset(token)
        return
    _LOG_CONTEXT.set({})


@contextmanager
def log_context(**values: Any):
    token = bind_log_context(**values)
    try:
        yield
    finally:
        clear_log_context(token)


def setup_logging(service: str = "terraform-manager", level: Optional[str] = None) -> None:
    """
    Configure structured logging once per process.

    Subsequent invocations no-op to avoid clobbering handlers (useful for dev-server reloads).
    """

    global _CONFIGURED, _SERVICE_NAME
    if _CONFIGURED:
        if service and service != _SERVICE_NAME:
            _install_service_record_factory(service)
            _SERVICE_NAME = service
        return

    log_level = (level or _default_level()).upper()
    handlers = _build_handlers(log_level)
    queue_handler = QueueHandler(_LOG_QUEUE)
    root = logging.getLogger()
    root.handlers = []
    root.addHandler(queue_handler)
    root.setLevel(log_level)
    root.propagate = False

    _start_listener(handlers)
    _install_service_record_factory(service)
    _SERVICE_NAME = service
    _CONFIGURED = True


def _default_level() -> str:
    return getenv("TFM_LOG_LEVEL", "INFO")


def _build_handlers(level: str) -> list[logging.Handler]:
    formatter = StructuredJsonFormatter()
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [stream_handler]

    file_path = _log_file_path()
    if file_path:
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=_log_file_max_bytes(),
            backupCount=_log_file_backup_count(),
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    return handlers


def _start_listener(handlers: list[logging.Handler]) -> None:
    global _QUEUE_LISTENER
    if _QUEUE_LISTENER is not None:
        return
    _QUEUE_LISTENER = QueueListener(_LOG_QUEUE, *handlers, respect_handler_level=True)
    _QUEUE_LISTENER.start()
    atexit.register(_stop_listener)


def _stop_listener() -> None:
    global _QUEUE_LISTENER
    if _QUEUE_LISTENER is None:
        return
    _QUEUE_LISTENER.stop()
    _QUEUE_LISTENER = None


def _log_file_path() -> Optional[str]:
    value = getenv("TFM_LOG_FILE")
    if value:
        lowered = value.strip().lower()
        if lowered in {"stdout", "stderr", "none", "off"}:
            return None
        path = Path(value)
    else:
        directory = Path(getenv("TFM_LOG_DIR", "logs"))
        path = directory / "terraform-manager.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def _log_file_max_bytes() -> int:
    raw = getenv("TFM_LOG_FILE_MAX_BYTES")
    if raw and raw.isdigit():
        return int(raw)
    return 5 * 1024 * 1024


def _log_file_backup_count() -> int:
    raw = getenv("TFM_LOG_FILE_BACKUP_COUNT")
    if raw and raw.isdigit():
        return int(raw)
    return 5


def _install_service_record_factory(service: str) -> None:
    def factory(*args, **kwargs):
        record = _RECORD_FACTORY(*args, **kwargs)
        setattr(record, "service", service)
        context_payload = get_log_context()
        if context_payload:
            setattr(record, "log_context", context_payload)
        return record

    logging.setLogRecordFactory(factory)


def get_logger(name: str) -> Logger:
    """
    Convenience accessor that ensures logging is initialised before returning a module logger.
    """

    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name)
