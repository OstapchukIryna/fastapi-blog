from blog.infrastructure import models
from blog.presentation.web.pages.feed import arrange
from blog.schemas import Pagination


def test_arrange_first_page_splits_lead_and_rest():
    a, b, c = models.Post(id=1), models.Post(id=2), models.Post(id=3)

    result = arrange([a, b, c], Pagination(skip=0))

    assert result == {"lead": a, "rest": [b, c]}


def test_arrange_first_page_empty_has_no_lead():
    result = arrange([], Pagination(skip=0))

    assert result == {"lead": None, "rest": []}


def test_arrange_deep_skip_has_no_lead():
    k, l, m = models.Post(id=1), models.Post(id=2), models.Post(id=3)

    result = arrange([k, l, m], Pagination(skip=10))

    assert result == {"lead": None, "rest": [k, l, m]}
