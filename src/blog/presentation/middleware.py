"""Что происходит с каждым запросом до и после того, как его обслужат.

Три ASGI-middleware, потому что три разные задачи и разное время
жизни: контекст нужен всему остальному, заголовки ставятся на выходе,
белый список отсекает на входе.

Всё это раньше делал nginx перед приложением. На Cloud Run своего
nginx нет — балансировщик Google даёт TLS и не знает ни про роуты, ни
про CSP, — поэтому логика переехала сюда. Заодно она стала переносимой:
одна и та же защита работает и за nginx, и без него.

! Плоский ASGI, не @app.middleware("http") / BaseHTTPMiddleware.
! Последний выполняет остаток конвейера в отдельной задаче anyio
! (BaseHTTPMiddleware.__call__ порождает её через task_group.start_soon),
! а contextvar, установленная в дочерней задаче, до родителя не
! добирается. Прямой await self.app(...) держит всё в одной задаче.
!
! Этого, впрочем, не хватило для user_id: FastAPI решает зависимости в
! собственном контексте, и set() внутри get_current_user наружу не
! всплывает. Отсюда scope["user_id"] — словарь ASGI переживает возврат
! из зависимости, в отличие от contextvar. request_id при этом работает
! через contextvar нормально: он ставится здесь и читается глубже, а не
! наоборот. Контекст течёт вниз, не вверх.
"""

import logging
import re
import secrets
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from blog.core.logging import SLOW_REQUEST_MS, request_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

# ! Входящий идентификатор проверяется: он
# ! попадает и в лог, и в заголовок ответа. Формат
# ! достаточно широк для uuid, ULID и трассировочных идентификаторов.
_VALID_REQUEST_ID = re.compile(r"\A[A-Za-z0-9._\-]{1,64}\Z")


class RequestContextMiddleware:
    """Помечает запрос, замеряет его, пишет одну строку, возвращает id."""

    def __init__(self, app: ASGIApp) -> None:
        """Обернуть приложение.

        Args:
            app (ASGIApp): остаток конвейера.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Провести один запрос через конвейер, не покидая эту задачу.

        Args:
            scope (Scope): область ASGI-соединения.
            receive (Receive): канал приёма.
            send (Send): канал отправки.
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
                extra={
                    "method": method,
                    "path": path,
                    "duration_ms": duration_ms,
                    # scope читается здесь, а не до вызова: значение
                    # появляется в нём во время обработки, не раньше.
                    "user_id": str(scope.get("user_id", "-")),
                },
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            # Уровень по последствию, а не по факту: успех — одна строка
            # на INFO, медленный или упавший запрос заметен без грепа,
            # промах по несуществующему адресу не засоряет вывод.
            if status_code >= 500 or duration_ms >= SLOW_REQUEST_MS:
                level = logging.WARNING
            elif status_code == 404:
                level = logging.DEBUG
            else:
                level = logging.INFO

            logger.log(
                level,
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
                    "user_id": str(scope.get("user_id", "-")),
                },
            )
        finally:
            request_id_var.reset(token)

    @staticmethod
    def _incoming_id(scope: Scope) -> str | None:
        """Прочитать X-Request-ID, если вызывающий прислал годный.

        Args:
            scope (Scope): область ASGI-соединения.

        Returns:
            str | None: значение заголовка, или None если его нет либо
                оно не проходит проверку формата.
        """
        wanted = REQUEST_ID_HEADER.lower().encode()
        for name, value in scope.get("headers", []):
            if name != wanted:
                continue
            candidate = value.decode("latin-1", errors="replace")
            return candidate if _VALID_REQUEST_ID.match(candidate) else None
        return None


class SecurityHeadersMiddleware:
    """Ставит заголовки безопасности и выдаёт nonce для инлайновых тегов.

    Раньше это делал nginx. Разница в том, где берётся nonce: там им
    служил $request_id, здесь он генерируется тут же и кладётся в scope,
    откуда его читают шаблоны. Одно значение на ответ, и оно же — в
    заголовке: браузер выполнит инлайновый тег, только если они совпали.

    Заголовки навешиваются на http.response.start, поэтому попадают и на
    страницы ошибок — там, где add_header без always их терял бы.
    """

    #: Заголовки, не зависящие от запроса. Собраны один раз, а не на
    #: каждый ответ: значения постоянные, а склейка байтов в горячем
    #: пути — работа без результата.
    STATIC_HEADERS: tuple[tuple[bytes, bytes], ...] = (
        (b"x-frame-options", b"SAMEORIGIN"),
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (
            b"strict-transport-security",
            b"max-age=63072000; includeSubDomains; preload",
        ),
    )

    def __init__(self, app: ASGIApp) -> None:
        """Обернуть приложение.

        Args:
            app (ASGIApp): остаток конвейера.
        """
        self.app = app

    def _policy(self, nonce: str) -> bytes:
        """Собрать Content-Security-Policy с этим nonce.

        Разрешено ровно то, чем страница пользуется: bootstrap с
        jsdelivr, шрифты Google, аватары из S3. Инлайновые теги проходят
        по nonce, а не по 'unsafe-inline' — иначе политика разрешала бы
        и тот скрипт, который вставил бы кто-то чужой.

        Args:
            nonce (str): значение, выданное этому ответу.

        Returns:
            bytes: значение заголовка.
        """
        return (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net; "
            f"style-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net "
            "https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://*.amazonaws.com; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'"
        ).encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Выдать nonce и навесить заголовки на ответ.

        Args:
            scope (Scope): область ASGI-соединения.
            receive (Receive): канал приёма.
            send (Send): канал отправки.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # token_urlsafe(16) — 128 бит: угадать значение за время жизни
        # одного ответа невозможно, а именно на этом держится вся
        # защита nonce.
        nonce = secrets.token_urlsafe(16)
        scope["csp_nonce"] = nonce
        policy = self._policy(nonce)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self.STATIC_HEADERS:
                    headers.append(name.decode(), value.decode())
                headers.append("content-security-policy", policy.decode())
            await send(message)

        await self.app(scope, receive, send_wrapper)


class PathAllowlistMiddleware:
    """Отсекает адреса, которых у приложения нет.

    Не про безопасность — несуществующий роут и так даёт 404. Про
    стоимость: сканеры перебирают чужие панели непрерывно, и на Cloud
    Run каждый такой запрос оплачивается временем выполнения. Ответ
    отсюда не будит ни маршрутизатор, ни зависимости.

    ! Белый список, а не чёрный. Адресов у приложения конечное число, и
    ! перечислить их надёжнее, чем догонять новые шаблоны: список
    ! устаревает при добавлении роута, что видно сразу, а не когда
    ! появится сканер с новым словарём.
    """

    ALLOWED_PREFIXES: tuple[str, ...] = (
        "/api",
        "/openapi.json",
        "/posts",
        "/tags",
        "/users",
        "/static",
        "/about",
        "/profile",
        "/login",
        "/register",
        "/forgot-password",
        "/reset-password",
        "/favicon.ico",
    )

    def __init__(self, app: ASGIApp) -> None:
        """Обернуть приложение.

        Args:
            app (ASGIApp): остаток конвейера.
        """
        self.app = app

    def _allowed(self, path: str) -> bool:
        """Обслуживается ли этот адрес.

        Args:
            path (str): путь из запроса.

        Returns:
            bool: True, если путь начинается с известного префикса.
        """
        if path == "/":
            return True
        return any(
            path == prefix or path.startswith(f"{prefix}/") for prefix in self.ALLOWED_PREFIXES
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Пропустить или ответить 404, не заходя в приложение.

        Args:
            scope (Scope): область ASGI-соединения.
            receive (Receive): канал приёма.
            send (Send): канал отправки.
        """
        if scope["type"] != "http" or self._allowed(scope["path"]):
            await self.app(scope, receive, send)
            return

        # 404, а не 444: обрыв соединения без ответа — трюк nginx,
        # которого в ASGI нет. Тело пустое, чтобы не тратить ничего на
        # оформление страницы для того, кто её не читает.
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"content-length", b"0")],
            }
        )
        await send({"type": "http.response.body", "body": b""})
