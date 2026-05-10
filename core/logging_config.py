from __future__ import annotations

import json
import logging
import logging.config
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.settings import Settings

# LogRecord 内置属性，不参与「结构化 extra」合并，避免污染 JSON
_LOG_RECORD_BUILTINS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "taskName",
        "asctime",
    }
)


def _record_extras(record: logging.LogRecord) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in _LOG_RECORD_BUILTINS or key.startswith("_"):
            continue
        if value is not None:
            out[key] = value
    return out


class JsonFormatter(logging.Formatter):
    """单行 JSON，便于 Loki / ELK 等采集。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = _record_extras(record)
        if extras:
            payload.update(extras)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """开发环境可读文本；将 logger.info(..., extra={...}) 中的字段附在行尾。"""

    default_time_format = "%Y-%m-%d %H:%M:%S"
    default_msec_format = "%s.%03d"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("fmt", "%(asctime)s %(levelname)s %(name)s %(message)s")
        super().__init__(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = _record_extras(record)
        if not extras:
            return base
        tail = " ".join(f"{k}={v!r}" for k, v in sorted(extras.items()))
        return f"{base} | {tail}"


def setup_logging(settings: Settings) -> None:
    """
    使用 dictConfig 统一根 logger 与 uvicorn 相关 logger。
    disable_existing_loggers=False，避免覆盖 Uvicorn 已创建的 logger。
    生产若同时使用 Uvicorn access 与 app.access，可能重复；可将 Uvicorn 启动为 --no-access-log。
    """
    fmt_key = "json" if settings.LOG_FORMAT == "json" else "text"
    level = settings.LOG_LEVEL.upper()

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": JsonFormatter},
            "text": {"()": TextFormatter},
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": fmt_key,
                "stream": sys.stderr,
            },
        },
        "root": {
            "level": level,
            "handlers": ["default"],
        },
        "loggers": {
            "uvicorn": {"level": "INFO", "handlers": [], "propagate": True},
            "uvicorn.access": {
                "level": "WARNING",
                "handlers": [],
                "propagate": True,
            },
            "uvicorn.error": {"level": "INFO", "handlers": [], "propagate": True},
        },
    }
    logging.config.dictConfig(config)
