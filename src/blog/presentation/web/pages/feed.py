"""What a paged page hands to its template, and how a batch is arranged.

Neither of these is a route, and that is why they are not in one. They are
the same kind of thing as `PostFormView` in web/forms.py: state computed
for a template, with the derivations that would otherwise be repeated in
Jinja or in four route bodies.

Kept out of listings.py so that the module holding the routes holds only
routes — and so this can be read without scrolling past them.
"""

from collections.abc import Sequence, Sized
from dataclasses import dataclass
from typing import Self

from fastapi import Request

from blog.infrastructure import models
from blog.schemas import Pagination


def arrange(items: Sequence[models.Post]) -> dict:
    """Split one batch into the post shown large and the ones below it.

    The pinned post is found by looking at the first element rather than
    by scanning, because the query already sorts pinned first. Scanning
    used to be necessary, and with pagination it also became wrong: on
    the second batch the pinned post is not in the slice at all, so the
    scan found nothing and an arbitrary post took the lead position.

    Args:
        items (Sequence[models.Post]): one batch, in query order.

    Returns:
        dict: the template context — `pinned` (only when the lead really
            is pinned), `lead`, and `rest`.
    """
    lead = items[0] if items else None
    return {
        "pinned": lead if lead is not None and lead.is_pinned else None,
        "lead": lead,
        "rest": list(items[1:]),
    }


@dataclass(slots=True, frozen=True)
class Feed:
    """What the "load more" button needs: where, how far, how many.

    Frozen because it describes one rendered response. It is built at the
    end of a route and read by the template; letting a field be assigned
    afterwards would allow an object claiming to have shown ten records
    while carrying the offset of twenty.

    Attributes:
        url (str): the same list under /api. Resolved through url_for by
            route name rather than written as a string, so the address
            is not a fact kept in two places that can disagree.
        shown (int): how many records are on the page already — and, by
            the same token, the offset the next request starts at.
        limit (int): how many to fetch per batch from here on.
        total (int): how many exist under this query.
    """

    url: str
    shown: int
    limit: int
    total: int

    @classmethod
    def after(
        cls,
        request: Request,
        route: str,
        page: Pagination,
        items: Sized,
        total: int,
        **path_params: object,
    ) -> Self:
        """Describe the feed a page has just rendered the first slice of.

        Args:
            request (Request): the request being answered; url_for lives on it.
            route (str): name of the JSON route that serves the same list.
            page (Pagination): the slice this page asked for.
            items (Sized): what came back, so the next offset can be worked out.
            total (int): how many records exist under the same query.
            **path_params: values the route needs in its path, such as the
                tag name or the author id. Passed through to url_for so the
                address is never assembled by hand in two places.

        Returns:
            Self: state the template hands to the "load more" button.
        """
        return cls(
            url=str(request.url_for(route, **path_params)),
            shown=page.skip + len(items),
            limit=page.limit,
            total=total,
        )

    @property
    def more(self) -> bool:
        """Whether anything is left to fetch."""
        return self.shown < self.total
