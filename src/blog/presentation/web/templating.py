"""The Jinja environment: where templates live and what they can reach.

Configured once at import. Everything registered here is available to
every template, which is the point — a value or a filter needed by three
pages should not be passed by three routes.
"""

from collections.abc import MutableMapping
from typing import Any

import markdown
from fastapi import Request
from fastapi.templating import Jinja2Templates

from blog.core.config import TEMPLATES_DIR

# Facts about the site itself rather than about any request: the byline,
# the contact links, the repository. A global because it is the same on
# every page, and threading it through sixteen routes would say nothing.
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

MARKDOWN_EXTENSIONS = ["fenced_code", "tables"]


def author_flag(request: Request) -> dict[str, Any]:
    """Tell every template whether the visitor may edit.

    A context processor rather than a route argument, because the answer
    is needed by the layout — the header decides what to show before any
    page-specific template runs.

    Args:
        request (Request): the request being rendered. Unused for now;
            it is the whole input the real check will need.

    Returns:
        dict[str, Any]: the flag, merged into every template context.

    # TODO: answer from the request instead of always saying yes. The
    # token lives in localStorage, so the server cannot see it — this
    # becomes answerable once the token also travels in a cookie.
    """
    return {"is_author": True}


templates = Jinja2Templates(directory=TEMPLATES_DIR, context_processors=[author_flag])

jinja_globals: MutableMapping[str, Any] = templates.env.globals
jinja_globals["site"] = SITE

# * Markdown is rendered at display time rather than stored as HTML, so a
# * change here applies to everything already published — and so the
# * database keeps the source the author actually wrote.
templates.env.filters["markdown"] = lambda text: markdown.markdown(
    text, extensions=MARKDOWN_EXTENSIONS
)
