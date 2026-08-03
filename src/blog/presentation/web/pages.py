"""
The HTML side of the site: every page a user opens in a browser.

Первая порция записей рисуется здесь, сервером. Следующие приезжают из
того же /api, который отвечает Postman'у, — страница только говорит
кнопке, откуда брать и сколько уже показано.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

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
from blog.schemas import PageParams, PostFormInput
from blog.services import posts, tags
from blog.services.auth import CurrentUser
from blog.services.posts import PostDep
from blog.services.users import UserDep

router = APIRouter(include_in_schema=False)


def arrange(items: Sequence[models.Post]) -> dict:
    """
    Split a slice into the one post at the top and the rest.

    Ищет закреплённый не перебором, а первым элементом: запрос уже
    отсортирован pinned-first. Раньше перебор был обязателен, потому что
    закреплённый мог оказаться где угодно, — а с пагинацией он ещё и
    выпадал из второй порции, и на второй странице в шапку попадал
    случайный пост.

    Args:
        items (Sequence[models.Post]): одна порция, в порядке запроса.

    Returns:
        dict: закреплённый (если он и есть первый), ведущий и остальные.

    """
    lead = items[0] if items else None
    return {
        "pinned": lead if lead is not None and lead.is_pinned else None,
        "lead": lead,
        "rest": list(items[1:]),
    }


@dataclass(slots=True)
class Feed:
    """
    Что нужно кнопке «ещё»: откуда брать, сколько показано, сколько всего.

    url считается через url_for по имени роута, а не пишется строкой:
    адрес API — не тот факт, который стоит держать в двух местах.

    Attributes:
        url (str): адрес того же списка в /api.
        shown (int): сколько записей уже на странице — и он же offset
            следующего запроса.
        limit (int): по сколько брать дальше.
        total (int): сколько всего под этот запрос.

    """

    url: str
    shown: int
    limit: int
    total: int

    @property
    def more(self) -> bool:
        return self.shown < self.total


# --- Routes ---------------------------------------------------------


@router.get("/", name="home")
@router.get("/posts", name="posts")
async def home(request: Request, db: DbSession, page: PageParams):
    items, total = await posts.list_all(db, page)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **arrange(items),
            "title": "Home",
            "feed": Feed(
                url=str(request.url_for("list_posts")),
                shown=page.skip + len(items),
                limit=page.limit,
                total=total,
            ),
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
    page's own script sends the fields to /api/posts instead. Moving the
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
async def toggle_pin(request: Request, post: PostDep, db: DbSession):
    await posts.set_pinned(db, post, pinned=not post.is_pinned)
    return RedirectResponse(
        request.url_for("edit_post", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/posts/{post_id}", name="post_page")
async def post_page(request: Request, post: PostDep, db: DbSession):
    related, related_label = await posts.find_related(db, post)
    return templates.TemplateResponse(
        request,
        "post.html",
        {
            "post": post,
            "related": related,
            "related_label": related_label,
            "title": post.title,
        },
    )


@router.get("/tags", name="tags_index")
async def tags_index(request: Request, db: DbSession, page: PageParams):
    rows, total = await tags.with_counts(db, page)
    return templates.TemplateResponse(
        request,
        "tags.html",
        {
            "tags": rows,
            "title": "Topics",
            "feed": Feed(
                url=str(request.url_for("list_tags")),
                shown=page.skip + len(rows),
                limit=page.limit,
                total=total,
            ),
        },
    )


@router.get("/tags/{tag}", name="get_tag")
async def get_tag(request: Request, tag: str, db: DbSession, page: PageParams):
    items, total = await posts.with_tag(db, tag, page)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **arrange(items),
            "filter_tag": tag,
            "title": f"#{tag}",
            "feed": Feed(
                url=str(request.url_for("get_tag_posts", tag=tag)),
                shown=page.skip + len(items),
                limit=page.limit,
                total=total,
            ),
        },
    )


@router.get("/users/{user_id}/posts", name="user_posts")
async def user_posts_page(
    request: Request, user: UserDep, db: DbSession, page: PageParams
):
    items, total = await posts.for_author(db, user.id, page)
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {
            "posts": items,
            "user": user,
            "title": f"{user.username}'s posts",
            "feed": Feed(
                url=str(request.url_for("get_user_posts", user_id=user.id)),
                shown=page.skip + len(items),
                limit=page.limit,
                total=total,
            ),
        },
    )


@router.get("/about", name="about")
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {"title": "About"})


@router.get("/profile", name="profile")
def profile(request: Request):
    return templates.TemplateResponse(request, "profile.html", {"title": "Profile"})


@router.get("/login", name="login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@router.get("/register", name="register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})


@router.post("/posts/{post_id}/delete", name="delete_post")
async def delete_post(post: PostDep, db: DbSession):
    await posts.delete(db, post)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
