"""Turning an exception into whatever the caller can read.

The same failure has two correct renderings. A script wants JSON with a
status; a browser wants a page it can look at. Which one is used is
decided by the path, because that is the only thing available at the
moment a handler runs that reliably says who is asking.
"""

import logging

from fastapi import FastAPI, Request, Response, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from blog.presentation.web.templating import templates

logger = logging.getLogger(__name__)

API_PATH_ROOT = "/api/"

GENERIC_FAILURE = "An error occurred. Please try again."
INVALID_REQUEST = "Invalid request. Please try again."


def error_page(request: Request, status_code: int, message: str) -> Response:
    """Render generic error page."""
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status_code,
            "title": f"Error {status_code}",
            "message": message,
        },
        status_code=status_code,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach the handlers to an application."""

    @app.exception_handler(StarletteHTTPException)
    async def general_http_exception_handler(
        request: Request, exception: StarletteHTTPException
    ) -> Response:
        """Answer any deliberate HTTP failure in the caller's own terms.

        Args:
            request (Request): the request that failed.
            exception (StarletteHTTPException): the raised refusal.

        Returns:
            Response: JSON under /api/, an HTML page everywhere else.
        """
        if exception.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.exception("Unhandled server-side refusal: %s", exception.detail)

        if request.url.path.startswith(API_PATH_ROOT):
            return await http_exception_handler(request, exception)

        return error_page(request, exception.status_code, exception.detail or GENERIC_FAILURE)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exception: RequestValidationError
    ) -> Response:
        """Answer a request what kind of validation error it is.

        Args:
            request (Request): the request that failed.
            exception (RequestValidationError): what Pydantic rejected..
        """
        if request.url.path.startswith(API_PATH_ROOT):
            return await request_validation_exception_handler(request, exception)

        return error_page(request, status.HTTP_422_UNPROCESSABLE_CONTENT, INVALID_REQUEST)
