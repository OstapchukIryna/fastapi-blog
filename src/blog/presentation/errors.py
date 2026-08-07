"""Turning an exception into whatever the caller can read.

The same failure has two correct renderings. A script wants JSON with a
status; a browser wants a page it can look at. Which one is used is
decided by the path, because that is the only thing available at the
moment a handler runs that reliably says who is asking.
"""

from fastapi import FastAPI, Request, Response, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from blog.presentation.web.templating import templates

# ! Written out rather than built from blog.presentation.api's API_PREFIX —
# ! this only needs to ask "is the caller a script or a browser", and every
# ! JSON route answers under this root regardless of what else changes there.
API_PATH_ROOT = "/api/"

GENERIC_FAILURE = "An error occurred. Please try again."
INVALID_REQUEST = "Invalid request. Please try again."


def error_page(request: Request, status_code: int, message: str) -> Response:
    """Render the shared error page."""
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
    """Attach the handlers to an application.

    Registered through a function rather than at import time, so this
    module never has to import `main` and no cycle appears.

    The handlers are declared with decorators rather than passed to
    `add_exception_handler`, because that method is typed as accepting
    `Callable[[Request, Exception], Response]`, and a strict checker
    rejects a handler that narrows the second argument to the exception
    it actually handles.

    Args:
        app (FastAPI): the application to attach to.
    """

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
        if request.url.path.startswith(API_PATH_ROOT):
            return await http_exception_handler(request, exception)

        return error_page(
            request, exception.status_code, exception.detail or GENERIC_FAILURE
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exception: RequestValidationError
    ) -> Response:
        """Answer a request whose shape was wrong.

        Args:
            request (Request): the request that failed.
            exception (RequestValidationError): what Pydantic rejected.

        Returns:
            Response: for the API, the framework's own detailed body,
                because a client can act on the field list. For a page,
                one sentence: the field-by-field breakdown belongs beside
                the inputs, and the form already does that itself.
        """
        if request.url.path.startswith(API_PATH_ROOT):
            return await request_validation_exception_handler(request, exception)

        return error_page(
            request, status.HTTP_422_UNPROCESSABLE_CONTENT, INVALID_REQUEST
        )
