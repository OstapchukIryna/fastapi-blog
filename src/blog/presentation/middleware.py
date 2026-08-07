"""Giving every request an id, and every log line it causes the same one.

Not a dependency's job: an incoming X-Request-ID is honoured (a caller
who already tracks its own id keeps it end to end), and one is minted
otherwise. The id lives in a contextvar rather than being threaded
through every function, because core.logging's RequestIDFilter reads it
from any logger anywhere in the call stack — a service raising an error
five layers down still gets stamped without knowing this middleware exists.
"""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from blog.core.logging import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Stamp the request, run it, echo the id back.

    Args:
        request (Request): the incoming request.
        call_next (Callable): the rest of the pipeline.

    Returns:
        Response: whatever call_next produced, with the id in a response
            header — so a caller reporting a problem can hand it over.
    """
    request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)

    response.headers[REQUEST_ID_HEADER] = request_id
    return response
