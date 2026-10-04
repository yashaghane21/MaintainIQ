"""Structured JSON logging with a per-request correlation ID."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Fields that callers may attach via `extra=` and that we want in the JSON line.
_EXTRA_FIELDS = (
    "endpoint", "method", "status_code", "duration_ms", "issue_id", "work_order_id",
    "document_id", "equipment_id", "ai_provider", "ai_status", "retrieval_status",
    "threshold_summary", "decision", "event",
)

# Defensive: never emit values for keys that look like secrets.
_SECRET_MARKERS = ("key", "secret", "password", "token")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                value = getattr(record, field)
                if any(m in field for m in _SECRET_MARKERS):
                    value = "***"
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Quiet noisy third-party loggers.
    for noisy in ("uvicorn.access", "httpx", "chromadb", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
