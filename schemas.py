from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    """Пароль сюда не входит намеренно: response_model отсекает всё,
    чего нет в схеме, поэтому хеш физически не попадёт в ответ."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    image_path: str


class PostForm(BaseModel):
    """Поля, которые вводит человек. HTML-форма и API проверяются
    одним и тем же кодом, поэтому правила не могут разойтись."""

    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=250)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip().lower() for t in value if t.strip()]
        # dict.fromkeys вместо set: убирает дубли, сохраняя порядок
        return list(dict.fromkeys(cleaned))


class PostCreate(PostForm):
    """То же плюс автор: в API его передаёт клиент, а в форме он
    берётся из сессии, поэтому в PostForm ему не место."""

    user_id: int


class PostResponse(BaseModel):
    """Ответ API для списка. Без content: выдача из десяти записей
    иначе тащит десять полных статей ради заголовков."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    summary: str
    date_posted: datetime
    is_pinned: bool
    tags: list[str]

    @field_validator("tags", mode="before")
    @classmethod
    def flatten_tags(cls, value):
        # mode="before" получает список объектов Tag из связи.
        # Наружу отдаём плоские строки: клиенту не нужна форма [{"name": ...}]
        return [t.name if hasattr(t, "name") else t for t in value]


class PostDetail(PostResponse):
    """Ответ API для одной записи. Тело есть только здесь."""

    content: str


class TagCount(BaseModel):
    name: str
    count: int
