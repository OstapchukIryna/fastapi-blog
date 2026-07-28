from pydantic import BaseModel, ConfigDict, Field


class PostBase(BaseModel):
    author: str = Field(min_length=3, max_length=50)
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=250)

    tags: list[str] = Field(default_factory=list)


class PostCreate(PostBase):
    content: str = Field(min_length=1)


class PostSummary(PostBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_posted: str


class PostResponse(PostSummary):
    # We need the body only there

    content: str
