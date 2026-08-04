"""Serving the files that ship with the repository.

A thin wrapper over Starlette's StaticFiles, for one reason: the default
sends `etag` and `last-modified` and no `cache-control` at all. Browsers
then apply heuristic caching — they guess a lifetime from how old the file
looks — and a returning visitor can run new HTML against an old script.
"""

from typing import Any

from starlette.responses import Response
from starlette.staticfiles import StaticFiles


class RevalidatedStaticFiles(StaticFiles):
    """Static files a browser must check before reusing.

    `no-cache` does not mean "do not store". It means "store it, but ask
    before you use it again" — and with the ETag the default already
    sends, the answer is almost always a 304 with no body. The cost is one
    conditional request per file per page load; what it buys is that a
    deploy cannot leave somebody running yesterday's JavaScript against
    today's markup.

    ! This is exactly the failure that made this class necessary. When
    ! /api moved to /api/v1, the pages started calling `${API}/users/me`
    ! while a cached utils.js had no `API` export at all. The module threw
    ! at import time, so the page rendered and then quietly did nothing —
    ! no error a visitor could see, no clue where to look.

    The alternative is a hash in the filename and a year-long cache, which
    is better for a site with real traffic and needs a build step to
    produce the hash. There is no build step here on purpose.
    """

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        """Add the revalidation header to whatever the base class built.

        Returns:
            Response: the file, with `cache-control: no-cache`.
        """
        response = super().file_response(*args, **kwargs)
        response.headers.setdefault("cache-control", "no-cache")
        return response
