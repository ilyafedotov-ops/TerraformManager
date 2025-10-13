from __future__ import annotations

import json
import logging
from logging import Logger
from logging.config import dictConfig
from datetime import datetime, timezone
from typing import Any, Dict, Optional


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
_RECORD_FACTORY = logging.getLogRecordFactory()


def setup_logging(service: str = "terraform-manager", level: Optional[str] = None) -> None:
    """
    Configure structured logging once per process.

    Subsequent invocations no-op to avoid clobbering handlers (useful for dev-server reloads).
    """

    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = (level or _default_level()).upper()
    handler_config = {
        "class": "logging.StreamHandler",
        "formatter": "json",
    }

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": StructuredJsonFormatter,
                }
            },
            "handlers": {
                "default": handler_config,
            },
            "root": {
                "handlers": ["default"],
                "level": log_level,
            },
        }
    )

    _install_service_record_factory(service)
    _CONFIGURED = True


def _default_level() -> str:
    from os import getenv

    return getenv("TFM_LOG_LEVEL", "INFO")


def _install_service_record_factory(service: str) -> None:
    def factory(*args, **kwargs):
        record = _RECORD_FACTORY(*args, **kwargs)
        setattr(record, "service", service)
        return record

    logging.setLogRecordFactory(factory)


def get_logger(name: str) -> Logger:
    """
    Convenience accessor that ensures logging is initialised before returning a module logger.
    """

    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name)
