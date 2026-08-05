"""The Jinja environment: where templates live and what they can reach.

Configured once at import. Everything registered here is available to
every template, which is the point — a value or a filter needed by three
pages should not be passed by three routes.
"""

from collections.abc import MutableMapping
from typing import Any

import markdown
from fastapi.templating import Jinja2Templates

from blog.core.config import SITE_HANDLE, SITE_NAME, TEMPLATES_DIR

# Facts about the site itself rather than about any request: the byline,
# the contact links, the repository. A global because it is the same on
# every page, and threading it through sixteen routes would say nothing.
#
# * The handle and the name come from core/config.py. Everything else here
# * is web-only — a mail footer has no use for a Telegram link — but those
# * two are also what signs an outgoing email, so they live one layer down
# * where both surfaces can read the same value.
SITE = {
    "handle": SITE_HANDLE,
    "name": SITE_NAME,
    "role": "backend Python dev",
    "now_updated": "28 Jul 2026",
    "github": "https://github.com/OstapchukIryna",
    "telegram": "https://t.me/parzifay",
    "email": "blue.hunde@gmail.com",
    "repo": "https://github.com/OstapchukIryna/fastapi-blog",
    "repo_label": "OstapchukIryna/fastapi-blog",
}

MARKDOWN_EXTENSIONS = ["fenced_code", "tables"]


# * There is no `is_author` in this context, and there deliberately is
# * not one. It used to be a context processor that always returned True,
# * because the token lives in localStorage where the server cannot see
# * it — a name that promised a check nobody was making.
# *
# * What actually hides the author-only controls is the browser, and it
# * already worked: `.nav-auth` is display:none until <head> sets
# * data-signed-in, and the edit link on a post carries data-author-only
# * with the author id for the layout script to compare. Removing the
# * flag removed a second mechanism that was doing nothing.
# *
# ! Neither is enforcement. /posts/{id}/edit and the API stay reachable
# ! to anyone who types the address; what stops them is the OwnedPost
# ! dependency on the server, not anything in a template. A real
# ! server-side answer needs the token in a cookie, which is a change to
# ! how sign-in works rather than a change here.
templates = Jinja2Templates(directory=TEMPLATES_DIR)

jinja_globals: MutableMapping[str, Any] = templates.env.globals
jinja_globals["site"] = SITE

# * Markdown is rendered at display time rather than stored as HTML, so a
# * change here applies to everything already published — and so the
# * database keeps the source the author actually wrote.
templates.env.filters["markdown"] = lambda text: markdown.markdown(
    text, extensions=MARKDOWN_EXTENSIONS
)
