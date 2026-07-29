from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from templating import templates


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

        message = (
            exception.detail
            if exception.detail
            else "An error occurred. Please check your request and try again."
        )

        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "status_code": exception.status_code,
                "title": f"Error {exception.status_code}",
                "message": message,
            },
            # Return the original status code from the exception, not a 200
            status_code=exception.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exception: RequestValidationError
    ):
        if request.url.path.startswith("/api/"):
            return await request_validation_exception_handler(request, exception)

        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
                "title": f"Error {status.HTTP_422_UNPROCESSABLE_CONTENT}",
                "message": "Invalid request. Please check your input and try again.",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
