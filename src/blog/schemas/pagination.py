"""
Срез: как его просят в запросе и как отдают в ответе.

Отдельный модуль, а не пара алиасов среди постов, по прозаической
причине: теги листаются ровно так же. Когда SkipDep жил в
services/posts.py, услуга тегов импортировала услугу постов, а та
импортировала теги обратно — и приложение переставало импортироваться.

Срез не принадлежит ни одной сущности. Он принадлежит границе, то есть
схемам, и оба сервиса берут его отсюда, не зная друг о друге.
"""

from collections.abc import Iterable
from typing import Annotated, Any, Self

from fastapi import Query
from pydantic import BaseModel, Field, computed_field

from blog.core.config import settings


class Pagination(BaseModel):
    """
    Сколько уже показано и сколько взять дальше.

    skip/limit, а не page/per_page: следующая порция приезжает кнопкой на
    той же странице, а не переходом на другую, и «сколько уже показано» —
    это буквально skip. Номер страницы пришлось бы держать во втором
    месте и умножать обратно.

    Потолок в 100 — не вкусовщина: без него один запрос с limit=100000
    вытаскивает всю таблицу вместе с joinedload автора.
    """

    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=settings.posts_per_page, ge=1, le=100)


# Модель за Query() описывает строку запроса так же, как модель за
# Form() описывает форму, а модель в теле — JSON. Роут пишет `page:
# PageParams` и получает уже проверенные числа.
PageParams = Annotated[Pagination, Query()]


class Page[T](BaseModel):
    """
    Порция и то, что нужно, чтобы попросить следующую.

    Один конверт на все списки: посты, посты автора, посты по тегу,
    теги. Раньше это были два одинаковых класса с разными именами полей,
    и любая правка одного молча расходилась со вторым.

    has_more считается здесь, а не у вызывающего. Арифметика ошибается на
    единицу ровно в тех местах, где её написали второй раз.
    """

    items: list[T]
    total: int
    skip: int
    limit: int

    @computed_field
    @property
    def has_more(self) -> bool:
        return self.skip + len(self.items) < self.total

    @classmethod
    def of(cls, items: Iterable[Any], total: int, page: Pagination) -> Self:
        """
        Собрать конверт из того, что вернул сервис.

        Звать нужно у параметризованного класса — `Page[PostResponse].of`,
        — тогда ORM-объекты проверяются в PostResponse прямо здесь. У
        голого Page параметр равен Any, и внутрь ляжет что угодно.
        """
        return cls(items=list(items), total=total, skip=page.skip, limit=page.limit)
