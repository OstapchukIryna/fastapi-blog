"""Configuring the standard library's logging.

Called once, at the top of main.py before any other blog module might log something.
"""

import json
import logging.config
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from blog.core.config import Settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)

# What a fresh LogRecord already carries, plus the two fields Formatter.format
# adds along the way — the boundary between "a field of the record itself"
# and "something a caller passed via extra=" and therefore worth surfacing
# as its own key in the JSON line.
_BUILTIN_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message",
    "asctime",
}


class ContextFilter(logging.Filter):
    """Stamps every record with who and what caused it.

    "-" outside of a request — startup, shutdown, a script — so the
    format string never has to special-case an absent field.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the current request id and user id to the record.

        Args:
            record (logging.LogRecord): the record about to be emitted.

        Returns:
            bool: always True — this filter only annotates, never drops.
        """
        record.request_id = request_id_var.get() or "-"
        record.user_id = user_id_var.get() or "-"
        return True


class JSONFormatter(logging.Formatter):
    """One JSON object per line — what a log aggregator actually reads.

    Hand-written rather than a dependency: the shape needed is a handful
    of fields plus whatever a caller adds, and a third-party formatter
    would cost more to configure than this costs to write.

    Anything passed as `extra={...}` to a log call — a canonical log
    line's method/path/status/duration, say — becomes its own top-level
    key rather than text buried in `message`, which is the whole point of
    a field being searchable.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Render one record as one JSON line.

        Args:
            record (logging.LogRecord): the record to render.

        Returns:
            str: the line, with no trailing newline — the handler adds one.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "user_id": getattr(record, "user_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _BUILTIN_RECORD_ATTRS and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Attach one handler to the root logger, and fold uvicorn's into it.

    Args:
        settings (Settings): read for `environment` and `log_level`.
    """
    formatter = "json" if settings.environment == "production" else "console"

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "context": {"()": "blog.core.logging.ContextFilter"},
            },
            "formatters": {
                "console": {
                    "()": "uvicorn.logging.DefaultFormatter",
                    "fmt": "%(levelprefix)s [req=%(request_id)s user=%(user_id)s]"
                    " %(name)s: %(message)s",
                },
                "json": {"()": "blog.core.logging.JSONFormatter"},
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter,
                    "filters": ["context"],
                },
            },
            "root": {"handlers": ["default"], "level": settings.log_level},
            "loggers": {
                # * uvicorn.error has no entry on purpose: it is a child
                # * logger of "uvicorn" with no handler of its own, so it
                # * propagates up to "uvicorn"'s handler by default — the
                # * same thing uvicorn's own config relies on. Giving it
                # * propagate: False here (as uvicorn does for the other
                # * two) would silently swallow every startup/shutdown
                # * line, since it would then have nowhere to go.
                "uvicorn": {
                    "handlers": ["default"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["default"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        }
    )
