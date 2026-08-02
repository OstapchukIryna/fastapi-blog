"""
The ORM classes, one module per table.

Раньше это был один models.py, и он оставался читаемым ровно потому, что
сущностей три. Разложено по файлам не ради размера, а ради направления
ссылок: теперь видно, что Tag ни от кого не зависит, Post зависит от
обоих, а User знает о Post только по имени.

Импортировать отсюда, а не из подмодулей: `from blog.infrastructure
import models`, дальше `models.Post`. Это же гарантирует, что к моменту
первого запроса зарегистрированы все три класса — SQLAlchemy разрешает
`Mapped[list["Post"]]` через свой реестр, а туда класс попадает только
после импорта модуля.
"""

from blog.infrastructure.models.post import Post
from blog.infrastructure.models.tag import Tag, post_tags
from blog.infrastructure.models.user import User

__all__ = ["Post", "Tag", "User", "post_tags"]
