"""
Structured JSON logging with automatic correlation-ID propagation.

Every log record emitted anywhere in the application (services, routers,
middleware, tasks) will include the `correlation_id` of the in-flight request
because JsonFormatter reads it from a ContextVar that
CorrelationIdMiddleware sets at the start of each request.
"""
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

# -- ContextVar shared between middleware and formatter -----------------------
# Default sentinel is an empty string so cold-start logs are still valid JSON.
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def set_correlation_id(value: str) -> None:
    """Called by CorrelationIdMiddleware at the start of every request."""
    _correlation_id_var.set(value)


def get_correlation_id() -> str:
    return _correlation_id_var.get()


# -- Formatter ----------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """
    Emits each log record as a compact, single-line JSON object.
    Compatible with ELK/Datadog/Cloud Logging ingest pipelines.
    """

    LEVEL_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": self.LEVEL_MAP.get(record.levelno, record.levelname),
            "logger": record.name,
            "message": record.getMessage(),
            "service": "evchargefinder",
            "environment": settings.ENVIRONMENT,
        }

        # Attach correlation ID from context — empty string is filtered out
        correlation_id = get_correlation_id()
        if correlation_id:
            payload["correlation_id"] = correlation_id

        # Attach exception info if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Allow callers to attach arbitrary extra keys via `extra={}`
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            } and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


# -- Setup entry-point --------------------------------------------------------

def setup_logging(level: Optional[str] = None) -> None:
    """
    Configure root logger with the JSON formatter.
    Call once at application startup, before any other code runs.
    """
    log_level_str = level or ("DEBUG" if settings.DEBUG else "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Structured JSON logging initialised",
        extra={"log_level": log_level_str},
    )
