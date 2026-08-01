from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from templating import templates


def error_page(request: Request, status_code: int, message: str):
    """The error page both handlers fall back to when the caller is a browser."""
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status_code,
            "title": f"Error {status_code}",
            "message": message,
        },
        # The original status code from the exception, not a 200
        status_code=status_code,
    )


def register_error_handlers(app: FastAPI) -> None:
    """
    Вешает обработчики на приложение.

    Через функцию, а не напрямую: модуль не импортирует main, поэтому
    циклической зависимости не возникает. Декораторы внутри, а не
    add_exception_handler, потому что тот типизирован как
    Callable[[Request, Exception], Response] — и строгий проверяльщик
    ругается на суженный тип второго аргумента.
    """

    @app.exception_handler(StarletteHTTPException)
    async def general_http_exception_handler(
        request: Request, exception: StarletteHTTPException
    ):

        if request.url.path.startswith("/api/"):
            return await http_exception_handler(request, exception)

        return error_page(
            request,
            exception.status_code,
            exception.detail
            or "An error occurred. Please check your request and try again.",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exception: RequestValidationError
    ):
        if request.url.path.startswith("/api/"):
            return await request_validation_exception_handler(request, exception)

        return error_page(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid request. Please check your input and try again.",
        )
