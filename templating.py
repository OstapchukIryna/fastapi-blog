from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import markdown
from fastapi import Request
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"

SITE = {
    "handle": "called_mad",
    "name": "Iryna Ostapchuk",
    "role": "backend Python dev",
    "now_updated": "28 Jul 2026",
    "github": "https://github.com/OstapchukIryna",
    "telegram": "https://t.me/parzifay",
    "email": "blue.hunde@gmail.com",
    "repo": "https://github.com/OstapchukIryna/fastapi-blog",
    "repo_label": "OstapchukIryna/fastapi-blog",
}


def author_flag(request: Request) -> dict[str, Any]:

    # TODO: заменить реальной проверкой пользователя из запроса
    return {"is_author": True}


templates = Jinja2Templates(directory=TEMPLATES_DIR, context_processors=[author_flag])

jinja_globals: MutableMapping[str, Any] = templates.env.globals
jinja_globals["site"] = SITE

templates.env.filters["markdown"] = lambda text: markdown.markdown(
    text, extensions=["fenced_code", "tables"]
)
