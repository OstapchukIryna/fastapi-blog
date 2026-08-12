"""Configuring the standard library's logging.

Called once, at the top of main.py before any other blog module might log
something.

Two formatters, one per audience. Development reads a terminal, so the
console format is aligned into columns and coloured by severity — a wall
of same-shaped lines is where a warning goes unnoticed. Production is
read by a machine, so every line is one JSON object and anything passed
through `extra=` becomes a searchable key rather than text inside a
sentence.

Which level a call belongs at, since the answer is not obvious and the
levels are worthless once everything lands on INFO:

    DEBUG     detail only useful while chasing something. Off in
              production; nothing here should be needed to explain an
              incident after the fact.
    INFO      the canonical request line, startup and shutdown. Things
              that happened as intended, one line each.
    WARNING   the request succeeded and something is nevertheless wrong:
              an orphaned avatar after S3 refused a delete, a lockout
              triggering, a slow response. Nobody is paged, somebody
              should look.
    ERROR     the request did not do what it promised — an unhandled
              exception, a database that stopped answering, a reset email
              that never went out.
    CRITICAL  unused on purpose. Reserved for "the process cannot
              continue", which this application has no case for.
"""

import json
import logging.config
import os
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from blog.core.config import Settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)

# Above this, a response is worth a second look even though it succeeded.
SLOW_REQUEST_MS = 500

# What a fresh LogRecord already carries, plus the two fields
# Formatter.format adds along the way — the boundary between "a field of
# the record itself" and "something a caller passed via extra=" and
# therefore worth surfacing as its own key in the JSON line.
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
        request_id = request_id_var.get()
        user_id = user_id_var.get()
        # `is None`, not `or`: user id 0 would read as absent otherwise.
        # No such row exists today, and a guard that depends on that is
        # a guard that breaks the day the sequence is reset.
        record.request_id = request_id if request_id is not None else "-"
        record.user_id = str(user_id) if user_id is not None else "-"
        return True


# --- Console -----------------------------------------------------------

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"

LEVEL_COLOURS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[1;37;41m",  # white on red
}

METHOD_COLOUR = "\033[35m"  # magenta


def supports_colour(stream: Any = None) -> bool:
    """Whether ANSI escapes will be read as colour rather than printed.

    Checks the stream the handler actually writes to. StreamHandler
    defaults to stderr, so asking about stdout — which is what most
    libraries do — gives the wrong answer as soon as one of the two is
    redirected and the other is not.

    NO_COLOR is honoured because it is the one convention every tool
    agrees on: set to anything at all, it means "plain text".

    Args:
        stream (Any): the stream to ask about; stderr when omitted.

    Returns:
        bool: True when colour is safe to emit.
    """
    if os.environ.get("NO_COLOR"):
        return False
    stream = stream if stream is not None else sys.stderr
    return bool(getattr(stream, "isatty", lambda: False)())


class ConsoleFormatter(logging.Formatter):
    """Aligned, coloured, one line per record — for a human at a terminal.

    Columns rather than a sentence, because the eye finds a level or a
    status by position long before it finds it by reading. The canonical
    request line gets its own rendering: method, path, status and
    duration are already separate fields on the record, so re-parsing
    them out of the message would be reading back what was just written.

    Colour is decided once, at construction, from the stream the handler
    writes to — not per record, and not from a global guess.
    """

    def __init__(self, *, colour: bool | None = None) -> None:
        """Build the formatter.

        Args:
            colour (bool | None): force colour on or off. Detected from
                the output stream when None, which is the usual case.
        """
        super().__init__()
        self.colour = supports_colour() if colour is None else colour

    def _paint(self, text: str, colour: str) -> str:
        return f"{colour}{text}{RESET}" if self.colour else text

    def _status(self, status_code: int) -> str:
        """Colour a status by class, so a 500 cannot look like a 200."""
        if status_code >= 500:
            return self._paint(str(status_code), LEVEL_COLOURS["ERROR"])
        if status_code >= 400:
            return self._paint(str(status_code), LEVEL_COLOURS["WARNING"])
        return self._paint(str(status_code), LEVEL_COLOURS["INFO"])

    def _duration(self, duration_ms: float) -> str:
        """Dim when unremarkable, yellow once it is worth noticing."""
        text = f"{duration_ms:.0f}ms"
        if duration_ms >= SLOW_REQUEST_MS:
            return self._paint(text, LEVEL_COLOURS["WARNING"])
        return self._paint(text, DIM)

    def _body(self, record: logging.LogRecord) -> str:
        """The message, with the request line rendered from its fields."""
        method = getattr(record, "method", None)
        path = getattr(record, "path", None)
        if method is None or path is None:
            return record.getMessage()

        line = f"{self._paint(method, METHOD_COLOUR)} {path}"

        status_code = getattr(record, "status_code", None)
        if status_code is not None:
            line += f" {self._paint('→', DIM)} {self._status(status_code)}"

        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            line += f" {self._duration(duration_ms)}"

        return line

    def format(self, record: logging.LogRecord) -> str:
        """Render one record as one aligned line.

        Args:
            record (logging.LogRecord): the record to render.

        Returns:
            str: the line, with no trailing newline.
        """
        stamp = datetime.fromtimestamp(record.created, tz=UTC).strftime("%H:%M:%S")
        level = self._paint(f"{record.levelname:<7}", LEVEL_COLOURS.get(record.levelname, ""))

        request_id = str(getattr(record, "request_id", "-"))
        user_id = str(getattr(record, "user_id", "-"))
        # First eight characters of a uuid are plenty to tell two
        # concurrent requests apart by eye, and a full one pushes the
        # message off the right of the terminal.
        context = self._paint(f"{request_id[:8]:<8} u={user_id:<3}", DIM)

        # The package prefix is on every line and therefore on none of
        # them: "services.posts" is what distinguishes this record.
        logger_name = record.name.removeprefix("blog.")
        origin = self._paint(f"{logger_name:<24}", DIM)

        line = f"{self._paint(stamp, DIM)} {level} {context} {origin} {self._body(record)}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# --- JSON --------------------------------------------------------------


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
            # From the record, not from now(): a queued record would
            # otherwise be stamped with the moment it was formatted.
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
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
                "console": {"()": "blog.core.logging.ConsoleFormatter"},
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
                # * WARNING, not INFO: RequestContextMiddleware already
                # * writes one line per request, with the request id and
                # * the duration this one lacks. Leaving both at INFO
                # * logs every request twice in two formats, and the
                # * copy without the id is the one that cannot be
                # * correlated with anything.
                "uvicorn.access": {
                    "handlers": ["default"],
                    "level": "WARNING",
                    "propagate": False,
                },
                # * SQLAlchemy's own echo is deliberately reachable
                # * without touching code: LOG_LEVEL=DEBUG turns on the
                # * canonical lines and leaves the queries off, which is
                # * usually what is wanted. Set this logger to INFO by
                # * hand for the afternoon spent chasing an N+1.
                "sqlalchemy.engine": {
                    "handlers": ["default"],
                    "level": "WARNING",
                    "propagate": False,
                },
            },
        }
    )
