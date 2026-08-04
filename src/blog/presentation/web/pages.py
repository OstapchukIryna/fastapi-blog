"""The HTML side of the site: every page a person opens in a browser.

The first batch of records is rendered here, by the server. Every batch
after it arrives from the same /api that answers Postman — the page only
tells the button where to fetch from and how many are already shown.

No query is written in this module. Both surfaces call services/, which
is why "post not found" reads identically on a page and in JSON.
"""

from collections.abc import Sequence, Sized
from dataclasses import dataclass
from typing import Annotated, Self

from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from blog.infrastructure import models
from blog.infrastructure.database import DbSession
from blog.presentation.web.forms import (
    PostFormView,
    form_errors,
    post_to_input,
    render_post_form,
)
from blog.presentation.web.templating import templates
from blog.schemas import PageParams, Pagination, PostFormInput
from blog.services import posts, tags
from blog.services.auth import CurrentUser
from blog.services.posts import PostDep
from blog.services.users import UserDep

router = APIRouter(include_in_schema=False)


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


# --- Routes ---------------------------------------------------------


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


# Must be declared before /posts/{post_id} because FastAPI parses routes in the order of registration,
# and "new" would otherwise match post_id: int
@router.get("/posts/new", name="new_post")
def new_post_form(request: Request) -> Response:
    """
    Show an empty form for a new post.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the blank form page.

    """
    return render_post_form(request, PostFormView(values=PostFormInput()))


@router.post("/posts/new", name="create_post_page")
async def create_post_page(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    submitted: Annotated[PostFormInput, Form()],
) -> Response:
    """
    Create a post from the submitted form.

    FastAPI fills PostFormInput itself: a model behind Form() describes a
    form the way a model in the body describes JSON.

    Unreachable from a browser at the moment, and kept rather than deleted
    because that is a property of where the token lives, not of this
    route. A plain form POST carries no Authorization header, and the token
    sits in localStorage, so CurrentUser can never be satisfied here — the
    page's own script sends the fields to /api/v1/posts instead. Moving the
    token into a cookie brings this path back with no change to the code
    below, which is why it stays.

    Args:
        request (Request): needed by the template and by url_for.
        current_user (CurrentUser): authorized current user.
        db (DbSession): current database session.
        submitted (PostFormInput): the fields as typed, unvalidated.

    Returns:
        Response: a 303 redirect to the new post, or the form again with
        errors and the typed text if validation failed.

    """
    try:
        form = submitted.validated()
    except ValidationError as exception:
        return render_post_form(
            request, PostFormView(values=submitted, errors=form_errors(exception))
        )

    post = await posts.create(db, form, current_user)
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/posts/{post_id}/edit", name="edit_post")
def edit_post_form(request: Request, post: PostDep) -> Response:
    """
    Show the edit form filled with an existing post.

    Args:
        request (Request): needed by the template.
        post (PostDep): the post being edited, resolved by the
            dependency, which raises 404 when it does not exist.

    Returns:
        Response: the form page populated from the post.

    """
    return render_post_form(
        request, PostFormView(values=post_to_input(post), post=post)
    )


@router.post("/posts/{post_id}/edit", name="update_post")
async def update_post(
    request: Request,
    post: PostDep,
    db: DbSession,
    submitted: Annotated[PostFormInput, Form()],
) -> Response:
    """
    Save an edit to a post.

    Args:
        request (Request): needed by the template and by url_for.
        post (PostDep): the post being edited.
        db (DbSession): current database session.
        submitted (PostFormInput): the fields as typed, unvalidated.

    Returns:
        Response: a 303 redirect to the post, or the form again with
        errors and the typed text if validation failed. The post is
        left untouched on failure, because the replacement happens after
        validation.

    """
    try:
        form = submitted.validated()
    except ValidationError as exception:
        return render_post_form(
            request,
            PostFormView(values=submitted, post=post, errors=form_errors(exception)),
        )

    await posts.replace(db, post, form)
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# One separate action, not a form field
@router.post("/posts/{post_id}/pin", name="toggle_pin")
async def toggle_pin(request: Request, post: PostDep, db: DbSession) -> Response:
    """Pin the post if it is not pinned, and unpin it if it is.

    A route of its own rather than a field on the edit form: pinning is
    one decision with one effect, and it should not require saving the
    rest of the post to take hold.

    Args:
        request (Request): needed to build the redirect target.
        post (PostDep): the post, or a 404.
        db (DbSession): request-scoped session.

    Returns:
        Response: a 303 back to the edit page, so a refresh re-reads the
            page rather than re-submitting the action.
    """
    await posts.set_pinned(db, post, pinned=not post.is_pinned)
    return RedirectResponse(
        request.url_for("edit_post", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/posts/{post_id}", name="post_page")
async def post_page(request: Request, post: PostDep, db: DbSession) -> Response:
    """Render one post, with a couple of suggestions underneath.

    Args:
        request (Request): the request being answered.
        post (PostDep): the post, or a 404.
        db (DbSession): request-scoped session.

    Returns:
        Response: the rendered article page.
    """
    related = await posts.find_related(db, post)
    # * A real match always shares at least one tag; a fallback never does.
    heading = "Related" if related and related[0].shared else "More posts"
    return templates.TemplateResponse(
        request,
        "post.html",
        {
            "post": post,
            "related": related,
            "related_label": heading,
            "title": post.title,
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


@router.get("/about", name="about")
def about(request: Request) -> Response:
    """Render the static about page.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page.
    """
    return templates.TemplateResponse(request, "about.html", {"title": "About"})


@router.get("/profile", name="profile")
def profile(request: Request) -> Response:
    """Render the profile shell.

    Deliberately empty of data: the token lives in localStorage, so the
    server cannot know whose profile this is. The page's own script
    fetches /api/v1/users/me and fills it in.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered shell.
    """
    return templates.TemplateResponse(request, "profile.html", {"title": "Profile"})


@router.get("/login", name="login")
def login_page(request: Request) -> Response:
    """Render the sign-in form.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page. The form posts to the API from the
            browser rather than to this route, because the answer is a
            token the server has nowhere to put.
    """
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@router.get("/register", name="register")
def register_page(request: Request) -> Response:
    """Render the registration form.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page.
    """
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})


# ! Named *_page, unlike the other pages here. Route names are unique
# ! across the whole application, and the API endpoints of the same
# ! purpose already hold `forgot_password` and `reset_password` — with
# ! the short names, url_for in a template silently returned /api/… .
@router.get("/forgot-password", name="forgot_password_page")
def forgot_password_page(request: Request) -> Response:
    """Render the form that asks for a reset link.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page. Like sign-in, it is a shell: the
            form posts to the API, because the answer is deliberately the
            same whether or not the address is known and the server has
            no session in which to remember which was asked.
    """
    return templates.TemplateResponse(
        request, "forgot_password.html", {"title": "Reset your password"}
    )


@router.get("/reset-password", name="reset_password_page")
def reset_password_page(request: Request) -> Response:
    """Render the form that sets a new password from an emailed link.

    The token is not read here. It stays in the query string and is sent
    by the page's own script, so it never reaches the server as part of a
    page request — where it would end up in access logs and in the
    Referer header of anything the page loads.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page.
    """
    return templates.TemplateResponse(
        request, "reset_password.html", {"title": "Choose a new password"}
    )


@router.post("/posts/{post_id}/delete", name="delete_post")
async def delete_post(post: PostDep, db: DbSession) -> Response:
    """Delete a post from the edit page and return to the front page.

    Args:
        post (PostDep): the post, or a 404.
        db (DbSession): request-scoped session.

    Returns:
        Response: a 303 to the front page. There is nothing left to show
            at the post's own address.
    """
    await posts.delete(db, post)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
