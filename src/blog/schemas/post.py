from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from blog.schemas.tag import normalise_tags
from blog.schemas.user import UserPublic


class PostForm(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=250)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return normalise_tags(value)


class PostCreate(PostForm):
    pass


class PostUpdate(BaseModel):
    """
    A partial change to a post, for PATCH.

    Every field is optional, and None means "not sent" rather than "set
    to null" — none of these columns is nullable, so there is nothing a
    null could sensibly mean. The caller applies only the fields that
    actually arrived, via model_dump(exclude_unset=True).

    The constraints still hold for whatever is sent: a title of "" is
    rejected the same way it is on create. Only the requirement to send
    the field at all is lifted.

    Attributes:
        title (str | None): new title, if changing it.
        summary (str | None): new summary, if changing it.
        content (str | None): new markdown body, if changing it.
        tags (list[str] | None): the complete new tag set, if changing
            it. Tags are replaced wholesale rather than merged, so
            sending [] clears them; omitting the field leaves them.

    """

    title: str | None = Field(default=None, min_length=1, max_length=100)
    summary: str | None = Field(default=None, min_length=1, max_length=250)
    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str] | None) -> list[str] | None:
        # Normalise submitted tags
        return None if value is None else normalise_tags(value)


class PostFormInput(BaseModel):
    """
    Raw input from the HTML form: exactly what the browser sent.

    A separate type from PostForm because they are different things.
    Everything here is a string and everything is optional — the form can
    be submitted empty, and that is a person's mistake to be shown back,
    not a programming error. Tags arrive as one string because HTML has
    no "list" field.

    The empty defaults are what makes a blank form: PostFormInput() with
    no arguments.

    Attributes:
        title (str): the post title as typed.
        summary (str): the summary as typed.
        content (str): the markdown body as typed.
        tags (str): tags as one comma-separated string.

    """

    title: str = ""
    summary: str = ""
    content: str = ""
    tags: str = ""

    def validated(self) -> PostForm:
        """
        Turn the raw input into a validated post.

        The tag string becomes a list here; the remaining rules are not
        duplicated but taken from PostForm, the same model the API
        validates against.

        Returns:
            PostForm: the validated fields, with tags split, lowercased
            and de-duplicated.

        Raises:
            ValidationError: if any field fails validation. The caller
                catches it and redraws the form with the errors.

        """
        return PostForm(
            title=self.title,
            summary=self.summary,
            content=self.content,
            tags=[
                part
                for part in (chunk.strip() for chunk in self.tags.split(","))
                if part
            ],
        )


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author: UserPublic
    title: str
    summary: str
    date_posted: datetime
    is_pinned: bool
    tags: list[str]

    @field_validator("tags", mode="before")
    @classmethod
    def flatten_tags(cls, value):
        return [t.name if hasattr(t, "name") else t for t in value]


class PostDetail(PostResponse):
    content: str


class PaginatedPostResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
