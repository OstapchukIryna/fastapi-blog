"""Configuring the standard library's logging, once, for the whole process.

Every logger in the process — ours and uvicorn's — ends up on the same
handler with the same formatter, so a log aggregator sees one shape
instead of two interleaved ones. Development gets a console line matched
to uvicorn's own; production gets one JSON object per line, because that
is what everything downstream of a container actually parses.

! Called once, at the top of main.py, before any other blog module might
! log something. Safe to call again — dictConfig is declarative, not
! additive, so a second call (uvicorn re-imports main.py per --reload
! child) just replaces the same state with itself.
"""

import json
import logging.config
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from blog.core.config import Settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIDFilter(logging.Filter):
    """Stamps every record with the id of the request that caused it.

    "-" outside of a request — startup, shutdown, a script — so the
    format string never has to special-case an absent field.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the current request id, or its absence, to the record.

        Args:
            record (logging.LogRecord): the record about to be emitted.

        Returns:
            bool: always True — this filter only annotates, never drops.
        """
        record.request_id = request_id_var.get() or "-"
        return True


class JSONFormatter(logging.Formatter):
    """One JSON object per line — what a log aggregator actually reads.

    Hand-written rather than a dependency: the shape needed is five
    fields, and a third-party formatter would cost more to configure than
    this costs to write.
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
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


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
                "request_id": {"()": "blog.core.logging.RequestIDFilter"},
            },
            "formatters": {
                "console": {
                    "()": "uvicorn.logging.DefaultFormatter",
                    "fmt": "%(levelprefix)s [%(request_id)s] %(name)s: %(message)s",
                },
                "json": {"()": "blog.core.logging.JSONFormatter"},
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter,
                    "filters": ["request_id"],
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
