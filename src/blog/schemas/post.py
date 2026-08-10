"""Posts as they cross the boundary — in from a client, out to one.

Four inbound shapes: a complete post (PostForm, aliased as PostCreate at
the API boundary), a partial change (PostUpdate), and info the browser
put in a form (PostFormInput).
"""

from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from blog.schemas.tag import normalise_tags
from blog.schemas.user import UserPublic

if TYPE_CHECKING:
    # Only ever used as a type hint on flatten_tags's parameter below,
    # which Pydantic never inspects at runtime — the field's real type
    # comes from PostResponse.tags itself. Nothing here needs the import
    # to exist once the process is running.
    from blog.infrastructure.models.tag import Tag

# * Declared once so PostForm and PostUpdate cannot drift: without this,
# * the same min_length and max_length would be written out twice each,
# * and a change to one call site silently leaves the other accepting
# * what the first now rejects - a PATCH taking a title a POST refuses.
Title = Annotated[str, Field(min_length=1, max_length=100)]
Summary = Annotated[str, Field(min_length=1, max_length=250)]
Content = Annotated[str, Field(min_length=1)]


class PostForm(BaseModel):
    """A complete post with all fields required.

    Attributes:
        title (str): headline.
        summary (str): the listing blurb.
        content (str): the body as Markdown.
        tags (list[str]): labels, cleaned on the way in.
    """

    title: Title
    summary: Summary
    content: Content
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return normalise_tags(value)


# * An assignment, not a subclass: PostCreate() and PostForm() used to be
# * two distinct types with nothing between them but a name - a second
# * entry in the OpenAPI document a reader had to compare to the first to
# * confirm they matched. This is the same class under a second name,
# * which is exactly what "alias" already meant.
PostCreate = PostForm


class PostUpdate(BaseModel):
    """A partial change to a post for PATCH."""

    title: Title | None = None
    summary: Summary | None = None
    content: Content | None = None
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str] | None) -> list[str] | None:
        """Clean the tags if any were sent and pass None through."""
        return None if value is None else normalise_tags(value)


class PostFormInput(BaseModel):
    """Raw input from the HTML form.

    A separate type from PostForm. Everything is a string and is optional. Can
    be submitted empty.

    The empty defaults are what makes a blank form: `PostFormInput()`
    with no arguments is the "new post" page.
    """

    title: str = ""
    summary: str = ""
    content: str = ""
    tags: str = ""

    def validated(self) -> PostForm:
        """Convert what was typed into a post that can be stored.

        Splitting the tag string is the only rule that belongs to forms
        alone. Everything else is delegated to PostForm — the same model
        the JSON API validates against — so the two surfaces cannot start
        accepting different things.

        Returns:
            PostForm: the validated post.
        """
        typed = (chunk.strip() for chunk in self.tags.split(","))
        return PostForm(
            title=self.title,
            summary=self.summary,
            content=self.content,
            tags=[tag for tag in typed if tag],
        )


class PostResponse(BaseModel):
    """A post as it appears in a list. No body text because of markdown."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    author: UserPublic
    title: str
    summary: str
    date_posted: datetime
    tags: list[str]

    reading_minutes: int

    @field_validator("tags", mode="before")
    @classmethod
    def flatten_tags(cls, value: "list[Tag] | list[str]") -> list[str]:
        """Accept either Tag rows or plain text.

        Runs before validation because at that point the value is still
        whatever the ORM handed over: a list of Tag objects on the way
        out, and a list of strings when a test builds the model directly.

        Args:
            value (list[Tag] | list[str]): tags as ORM rows on the way
                out of the database, or as plain strings when a test
                builds the model directly.

        Returns:
            list[str]: tag names.
        """
        return [tag if isinstance(tag, str) else tag.name for tag in value]


class PostDetail(PostResponse):
    """A single post, with its body, the Markdown itself."""

    content: str
