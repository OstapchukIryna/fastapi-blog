from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from blog.infrastructure.database import Base

if TYPE_CHECKING:
    from blog.infrastructure.models.post import Post

# many-to-many table without class
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )

    # Post импортирован только под TYPE_CHECKING: он импортирует этот
    # модуль ради post_tags, и обратный импорт был бы циклом. В рантайме
    # имени Post здесь нет, и это работает — с Python 3.14 аннотации не
    # вычисляются при объявлении класса (PEP 649), а SQLAlchemy разрешает
    # имя через свой реестр, куда класс попадает при импорте пакета.
    # Проверено отдельной пробой: без кавычек и без импорта — configure_mappers() проходит.
    posts: Mapped[list[Post]] = relationship(secondary=post_tags, back_populates="tags")
