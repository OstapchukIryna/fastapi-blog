"""One post: reading it, writing it, and editing it.

The forms' own submit handlers post straight to the JSON API — the token
lives in localStorage, which a plain form POST here has no way to send —
so this module only renders pages. The routes that used to *accept* those
submissions (create, edit, delete) were deleted rather than kept
unreachable: they answered nothing a browser could ever call while the
token stays in localStorage, and git history is where they belong until
the token moves to a cookie and they have a caller again.

! Registration order matters inside this module. FastAPI matches in the
! order routes were added, so `/posts/new` has to be declared before
! `/posts/{post_id}` or "new" is parsed as a post id and answers 422.
"""

from fastapi import APIRouter, Request, Response

from blog.infrastructure.database import DbSession
from blog.presentation.web.forms import PostFormView, post_to_input, render_post_form
from blog.presentation.web.templating import templates
from blog.schemas import PostFormInput
from blog.services import posts
from blog.services.posts import PostDep

router = APIRouter()


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
    return render_post_form(request, PostFormView(values=post_to_input(post), post=post))


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
