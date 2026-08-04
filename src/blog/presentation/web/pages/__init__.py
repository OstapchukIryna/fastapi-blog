"""The HTML side of the site: every page a person opens in a browser.

One module was 18 routes long and held three unrelated jobs. They are now
three, split by what a route *does* rather than by the entity it mentions:

    listings.py  lists with a "load more" button — home, tags, one tag,
                 one author. Each renders the first batch and describes
                 where the rest comes from.
    posts.py     the article page and everything that changes a post:
                 the form, the edit, the pin, the delete.
    shells.py    pages rendered with no data at all, because the token
                 lives in localStorage and the script fills them in.
    feed.py      not routes: the state a paged template is handed.

The first batch of records is rendered by the server. Every batch after it
arrives from the same /api that answers Postman — the page only tells the
button where to fetch from and how many are already shown.

No query is written in this package. Both surfaces call services/, which
is why "post not found" reads identically on a page and in JSON.

This file exists to be the one router `main` mounts, so the split is
invisible from outside and can change again without touching main.py.
"""

from fastapi import APIRouter

from blog.presentation.web.pages import listings, posts, shells

# * include_in_schema once, here, rather than on each sub-router: these
# * are addresses a person types, not an API surface, and keeping them out
# * of /openapi.json is what lets the contract test compare like with like.
router = APIRouter(include_in_schema=False)

# ! Order is part of the behaviour. FastAPI matches routes in the order
# ! they were added, so a fixed path must be registered before a path
# ! parameter that would also match it — `/posts/new` before
# ! `/posts/{post_id}`. Within posts.py that order is preserved; across
# ! the three there is nothing that overlaps, and adding something that
# ! does means thinking about this line.
router.include_router(listings.router)
router.include_router(posts.router)
router.include_router(shells.router)
