from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
    def general_http_exception_handler(
        request: Request, exception: StarletteHTTPException
    ):
        message = (
            exception.detail
            if exception.detail
            else "An error occurred. Please check your request and try again."
        )

        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=exception.status_code,
                content={"detail": message},
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
    def validation_exception_handler(
        request: Request, exception: RequestValidationError
    ):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"detail": jsonable_encoder(exception.errors())},
            )

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
