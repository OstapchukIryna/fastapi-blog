"""Giving every request an id, and one summary line once it is done.

Not a dependency's job: an incoming X-Request-ID is honoured (a caller
who already tracks its own id keeps it end to end), and one is minted
otherwise. The id lives in a contextvar rather than being threaded
through every function, because core.logging's ContextFilter reads it
from any logger anywhere in the call stack — a service raising an error
five layers down still gets stamped without knowing this middleware exists.

The one line this module logs per request is a canonical log line: method,
path, status, how long it took — one place to look, rather than piecing a
request back together from whatever happened to log along the way.

! Plain ASGI, not @app.middleware("http") / BaseHTTPMiddleware. The latter
! runs the rest of the pipeline in a separate anyio task
! (starlette.middleware.base.BaseHTTPMiddleware.__call__ spawns one via
! task_group.start_soon), and a contextvar set inside a child task never
! reaches back out to its parent — user_id_var, set deep inside
! get_current_user, would still read as unset by the time this module's
! own log line runs. Awaiting self.app(...) directly keeps everything in
! one task, so a mutation downstream is visible up here.
"""

import logging
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from blog.core.logging import request_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware:
    """Stamps the request, times it, logs one line, echoes the id back."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the application.

        Args:
            app (ASGIApp): the rest of the pipeline.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run one request through the pipeline, in this same task.

        Args:
            scope (Scope): the ASGI connection scope.
            receive (Receive): the ASGI receive channel.
            send (Send): the ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._incoming_id(scope) or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 0

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers.append(REQUEST_ID_HEADER, request_id)
            await send(message)

        method = scope["method"]
        path = scope["path"]

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.exception(
                "%s %s -> unhandled (%sms)",
                method,
                path,
                duration_ms,
                extra={"method": method, "path": path, "duration_ms": duration_ms},
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.info(
                "%s %s -> %s (%sms)",
                method,
                path,
                status_code,
                duration_ms,
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
        finally:
            request_id_var.reset(token)

    @staticmethod
    def _incoming_id(scope: Scope) -> str | None:
        """Read X-Request-ID off the raw ASGI headers, if the caller sent one.

        Args:
            scope (Scope): the ASGI connection scope.

        Returns:
            str | None: the header's value, or None if absent.
        """
        wanted = REQUEST_ID_HEADER.lower().encode()
        for name, value in scope.get("headers", []):
            if name == wanted:
                return value.decode()
        return None
