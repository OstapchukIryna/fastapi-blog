"""The post form's state, and how that state becomes a page.

Separate from pages.py because this is the only place on the site where
what is rendered depends not just on the database but on what a person
has just typed and what the validator made of it. The routes are left
with two steps: obtain the state, render it.
"""

from dataclasses import dataclass, field

from fastapi import Request, Response, status
from pydantic import ValidationError

from blog.infrastructure import models
from blog.presentation.web.templating import templates
from blog.schemas import PostFormInput


@dataclass(slots=True)
class PostFormView:
    """
    State of the post form, from which the page is drawn.

    Prevents passing too much arguments in functions and routs

    Three fields instead of the previous six arguments. Two of the old
    ones are derived rather than passed: editing means "there is a post",
    and 422 means "there are errors". Before, `mode="edit"` with
    `post=None`, or errors alongside a 200, were both constructible and
    nothing prevented it.

    Attributes:
        values (PostFormInput): what the person typed. Returned to the
            fields even when the post was not saved, so typed text is
            never lost.
        post (models.Post | None): the post being edited, or None when
            creating a new one.
        errors (dict[str, str]): field name to message, one per field.

    """

    values: PostFormInput
    post: models.Post | None = None
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def editing(self) -> bool:
        """Whether this form is editing an existing post or starting one.

        Derived rather than passed, so "edit mode with no post" is not a
        state anybody can construct by accident.

        Returns:
            bool: True when a post is being edited.
        """
        return self.post is not None

    @property
    def title(self) -> str:
        """The heading, which is also the browser tab's title.

        Returns:
            str: wording that matches what the form is actually doing.
        """
        return "Edit post" if self.editing else "New post"

    @property
    def status_code(self) -> int:
        """The status the form should be returned with.

        Derived from whether there are errors, so a page showing
        complaints cannot be served as a 200 — which would tell a client,
        a cache and a crawler that the submission succeeded.

        Returns:
            int: 422 when the view carries errors, 200 otherwise.
        """
        return status.HTTP_422_UNPROCESSABLE_CONTENT if self.errors else status.HTTP_200_OK


def post_to_input(post: models.Post) -> PostFormInput:
    """Turn a stored post back into the strings its form fields show.

    The inverse of what the browser sends: tags become one comma-joined
    string again, because that is the only shape an HTML text field has.

    Args:
        post (models.Post): the post being edited.

    Returns:
        PostFormInput: field values, ready to be rendered into the form.
    """
    return PostFormInput(
        title=post.title,
        summary=post.summary,
        content=post.content,
        tags=", ".join(tag.name for tag in post.tags),
    )


def form_errors(exception: ValidationError) -> dict[str, str]:
    """
    Generate human-readable exeptions

    Args:
        exception (ValidationError): exeption from pydantic validation

    Returns:
        dict[str, str]: dictionary with field name and error message

    """
    errors: dict[str, str] = {}
    for error in exception.errors():
        field = str(error["loc"][0]) if error["loc"] else "form"
        context = error.get("ctx", {})
        kind = error["type"]

        if kind == "string_too_short" and context.get("min_length") == 1:
            message = "Required."
        elif kind == "string_too_short":
            message = f"At least {context['min_length']} characters."
        elif kind == "string_too_long":
            message = f"At most {context['max_length']} characters."
        else:
            message = error["msg"]

        errors.setdefault(field, message)
    return errors


def render_post_form(request: Request, view: PostFormView) -> Response:
    """
    Draw the post form in the given state.

    Serves both creating and editing: the fields are identical,
    and the differences — heading, submit target, button label — are
    derived from the view.

    Args:
        request (Request): needed by Jinja2Templates and url_for.
        view (PostFormView): typed values, the post being edited, and errors if exist.

    Returns:
        Response: the form page, with status 422 if the view holds errors.

    """
    return templates.TemplateResponse(
        request,
        "post_form.html",
        {"view": view, "title": view.title},
        status_code=view.status_code,
    )
