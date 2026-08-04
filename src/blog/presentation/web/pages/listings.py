"""Pages that show a list: the front page, the tags, one tag, one author.

Four routes with one shape between them. Each asks a service for a slice,
arranges it, and describes the feed the "load more" button continues — and
the first batch is rendered here while every batch after it comes from the
same /api that answers Postman.

No query is written in this module, and none in any of its siblings. Both
surfaces call services/, which is why "tag not found" reads identically on
a page and in JSON.
"""

from fastapi import APIRouter, Request, Response

from blog.infrastructure.database import DbSession
from blog.presentation.web.pages.feed import Feed, arrange
from blog.presentation.web.templating import templates
from blog.schemas import PageParams
from blog.services import posts, tags
from blog.services.users import UserDep

router = APIRouter()


@router.get("/", name="home")
@router.get("/posts", name="posts")
async def home(request: Request, db: DbSession, page: PageParams) -> Response:
    """Render the front page: the lead post and the start of the archive.

    Args:
        request (Request): the request being answered.
        db (DbSession): request-scoped session.
        page (PageParams): which slice to render. Usually the first, but
            a deep link with ?skip= renders that slice server-side.

    Returns:
        Response: the rendered home page.
    """
    items, total = await posts.list_all(db, page)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **arrange(items),
            "title": "Home",
            "feed": Feed.after(request, "list_posts", page, items, total),
        },
    )


@router.get("/tags", name="tags_index")
async def tags_index(request: Request, db: DbSession, page: PageParams) -> Response:
    """Render the index of tags with their post counts.

    Args:
        request (Request): the request being answered.
        db (DbSession): request-scoped session.
        page (PageParams): which slice of tags to render.

    Returns:
        Response: the rendered topics page.
    """
    rows, total = await tags.with_counts(db, page)
    return templates.TemplateResponse(
        request,
        "tags.html",
        {
            "tags": rows,
            "title": "Topics",
            "feed": Feed.after(request, "list_tags", page, rows, total),
        },
    )


@router.get("/tags/{tag}", name="get_tag")
async def get_tag(
    request: Request, tag: str, db: DbSession, page: PageParams
) -> Response:
    """Render the posts filed under one tag.

    Reuses home.html rather than having a template of its own: the two
    show the same list, and the only difference is the header, which the
    template picks from `filter_tag`.

    Args:
        request (Request): the request being answered.
        tag (str): the tag, from the path.
        db (DbSession): request-scoped session.
        page (PageParams): which slice to render.

    Returns:
        Response: the rendered list page.

    Raises:
        HTTPException: 404 when no post anywhere carries the tag.
    """
    items, total = await posts.with_tag(db, tag, page)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **arrange(items),
            "filter_tag": tag,
            "title": f"#{tag}",
            "feed": Feed.after(request, "get_tag_posts", page, items, total, tag=tag),
        },
    )


@router.get("/users/{user_id}/posts", name="user_posts")
async def user_posts_page(
    request: Request, user: UserDep, db: DbSession, page: PageParams
) -> Response:
    """Render everything one person has written.

    Args:
        request (Request): the request being answered.
        user (UserDep): the author, or a 404.
        db (DbSession): request-scoped session.
        page (PageParams): which slice to render.

    Returns:
        Response: the rendered author page.
    """
    items, total = await posts.for_author(db, user.id, page)
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {
            "posts": items,
            "user": user,
            "title": f"{user.username}'s posts",
            "feed": Feed.after(
                request, "get_user_posts", page, items, total, user_id=user.id
            ),
        },
    )
