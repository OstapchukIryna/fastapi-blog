from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import markdown
from fastapi import Request
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Личность и контакты в одном месте. Шаблоны рисуют только заполненные
# каналы, поэтому пустая строка = канала просто нет на сайте. Так на
# странице физически не может появиться ссылка, ведущая в никуда.
SITE = {
    "handle": "called_mad",
    "name": "Iryna",
    "role": "backend Python",
    # Дата правится руками вместе с блоком Now. Не datetime.now():
    # автоматическая дата врала бы о свежести того, что под ней написано.
    "now_updated": "28 Jul 2026",
    "github": "https://github.com/OstapchukIryna",
    "telegram": "https://t.me/parzifay",
    "email": "blue.hunde@gmail.com",
    # Исходник самого сайта. Для бэкенд-портфолио это главный экспонат:
    # работа, которую не видно на экране, видна в репозитории.
    "repo": "https://github.com/OstapchukIryna/fastapi-blog",
    "repo_label": "OstapchukIryna/fastapi-blog",
}


def author_flag(request: Request) -> dict[str, Any]:
    """Права автора для шаблонов.

    Процессор контекста, а не глобальная переменная, именно потому,
    что ответ обязан зависеть от запроса. Пока прав нет ни у кого и
    значение захардкожено — но когда появится JWT, правится только
    тело этой функции, а не каждый роут и шаблон.
    """
    # TODO: заменить реальной проверкой пользователя из запроса
    return {"is_author": True}


templates = Jinja2Templates(directory=TEMPLATES_DIR, context_processors=[author_flag])

# Именно globals, а не context_processors: макросы из _contact.html
# подключаются через {% import %} и контекст запроса не видят, а
# globals доступны им всегда.
# Jinja не аннотирует Environment.globals, поэтому его тип выводится из
# состава DEFAULT_NAMESPACE и новый ключ не проходит проверку типов.
# Сужаем к тому контракту, который Jinja декларирует у себя в load().
jinja_globals: MutableMapping[str, Any] = templates.env.globals
jinja_globals["site"] = SITE

templates.env.filters["markdown"] = lambda text: markdown.markdown(
    text, extensions=["fenced_code", "tables"]
)
