"""Posts as they cross the boundary — in from a client, out to one.

Four inbound shapes rather than one, because they describe genuinely
different situations: a complete post (PostForm and its API alias
PostCreate), a partial change (PostUpdate), and whatever the browser put
in a form (PostFormInput). Collapsing them would mean one model whose
rules depend on which endpoint is using it.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from blog.infrastructure.models.tag import Tag
from blog.schemas.tag import normalise_tags
from blog.schemas.user import UserPublic


class PostForm(BaseModel):
    """A complete post: everything needed to store one.

    Attributes:
        title (str): headline.
        summary (str): the listing blurb.
        content (str): the body, as Markdown.
        tags (list[str]): labels, cleaned on the way in.
    """

    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=250)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        """Apply the shared tag rules to whatever was submitted.

        Args:
            value (list[str]): tags as received.

        Returns:
            list[str]: stripped, lower-cased, de-duplicated.
        """
        return normalise_tags(value)


class PostCreate(PostForm):
    """The JSON body of a create or a full replace.

    A name rather than a new shape: creating and replacing take the same
    complete post, but the routes read better naming what they expect,
    and the OpenAPI document gets a schema per operation.
    """


class PostUpdate(BaseModel):
    """A partial change to a post, for PATCH.

    Every field is optional, and None means "not sent" rather than "set
    to null" — none of these columns is nullable, so there is nothing a
    null could sensibly mean. The service applies only the fields that
    actually arrived.

    The constraints still hold for whatever is sent: a title of "" is
    rejected exactly as it is on create. Only the requirement to send the
    field at all is lifted.

    Attributes:
        title (str | None): new title, if changing it.
        summary (str | None): new summary, if changing it.
        content (str | None): new Markdown body, if changing it.
        tags (list[str] | None): the complete new tag set, if changing
            it. Tags are replaced wholesale rather than merged, so
            sending [] clears them and omitting the field leaves them.
            The trade is that one tag cannot be added without naming the
            others; the alternative is two more endpoints.
    """

    title: str | None = Field(default=None, min_length=1, max_length=100)
    summary: str | None = Field(default=None, min_length=1, max_length=250)
    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str] | None) -> list[str] | None:
        """Clean the tags if any were sent, and pass None through.

        Args:
            value (list[str] | None): tags as received, or None.

        Returns:
            list[str] | None: cleaned tags, or None when the field was
                not sent at all — the distinction the whole model rests
                on, so it must survive validation.
        """
        return None if value is None else normalise_tags(value)


class PostFormInput(BaseModel):
    """Raw input from the HTML form: exactly what the browser sent.

    A separate type from PostForm because they describe different things.
    Everything here is a string and everything is optional — a form can
    be submitted empty, and that is a person's mistake to be shown back
    to them, not a programming error to raise on. Tags arrive as one
    string because HTML has no list field.

    The empty defaults are what makes a blank form: `PostFormInput()`
    with no arguments is the "new post" page.

    Attributes:
        title (str): the title as typed.
        summary (str): the summary as typed.
        content (str): the Markdown body as typed.
        tags (str): tags as one comma-separated string.
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

        Raises:
            ValidationError: when any field fails. The page catches it
                and redraws the form with the messages and the text the
                person had already typed.
        """
        typed = (chunk.strip() for chunk in self.tags.split(","))
        return PostForm(
            title=self.title,
            summary=self.summary,
            content=self.content,
            tags=[tag for tag in typed if tag],
        )


class PostResponse(BaseModel):
    """A post as it appears in a list.

    Carries no body text: that is PostDetail's job, and sending the full
    Markdown of forty posts to render forty cards would be most of the
    payload for none of the display.

    Attributes:
        id (int): the post's id.
        author (UserPublic): embedded, not just an id, so a card can be
            drawn from one response.
        title (str): headline.
        summary (str): the listing blurb.
        date_posted (datetime): publication time, in UTC.
        is_pinned (bool): whether this is the front page's lead.
        tags (list[str]): plain names rather than objects.
        reading_minutes (int): from the model's property.
        outline (list[str]): from the model's property.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    author: UserPublic
    title: str
    summary: str
    date_posted: datetime
    is_pinned: bool
    tags: list[str]

    # * Both come from model properties by way of from_attributes. They
    # * are here not for completeness but because the archive card is
    # * drawn by two renderers — Jinja for the first batch, JavaScript for
    # * every batch after it — and the two must not differ.
    reading_minutes: int
    outline: list[str]

    @field_validator("tags", mode="before")
    @classmethod
    def flatten_tags(cls, value: list[Tag] | list[str]) -> list[str]:
        """Accept either Tag rows or plain names.

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
    """A single post, with its body.

    Attributes:
        content (str): the Markdown source. Rendered by whoever displays
            it, so a client is free to show it another way.
    """

    content: str
