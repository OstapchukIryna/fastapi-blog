# --- Сборка ------------------------------------------------------------
FROM python:3.14.6-slim-bookworm AS builder

# uv из официального образа: копирование бинарника вместо установки
# через pip — быстрее и не тянет ничего лишнего в слой.
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
# Не скачивать интерпретатор: он уже есть в базовом образе, и вторая
# копия только раздула бы результат.
ENV UV_PYTHON_DOWNLOADS=0

# * Зависимости отдельным слоем, до кода приложения. Docker
# * переиспользует слой, пока не изменились его входные данные, поэтому
# * правка в services/posts.py не запускает установку заново — она
# * происходит только когда меняется pyproject.toml или uv.lock.
# *
# * --no-install-project обязателен: исходников пакета на этом шаге ещё
# * нет, и uv попытался бы установить то, чего не существует.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY . ./
RUN uv sync --locked --no-dev


# --- Выполнение --------------------------------------------------------
FROM python:3.14.6-slim-bookworm

WORKDIR /app

# * Пользователь создаётся до копирования, а переключение на него —
# * последней строкой перед CMD: USER действует на все инструкции ниже,
# * и любой RUN, добавленный после него, выполнялся бы без прав.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH"
# Без буферизации, иначе логи задерживаются в буфере и docker logs
# показывает их с опозданием — или не показывает вовсе при падении.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV PORT=8000

ENV FORWARDED_ALLOW_IPS=""

EXPOSE 8000

# Проверяется тот же /api/health, который в приложении ходит в базу на
# отдельном соединении: контейнер считается готовым, когда отвечает
# приложение вместе с базой, а не когда просто запустился процесс.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

USER appuser

# exec заменяет процесс оболочки, поэтому SIGTERM от docker stop доходит
# до fastapi — иначе оболочка проглотила бы его, и контейнер убивали бы
# по таймауту, оборвав соединения и не закрыв пул.
CMD ["/bin/sh", "-c", "exec fastapi run --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips=\"$FORWARDED_ALLOW_IPS\""]