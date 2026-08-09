from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from blog.infrastructure.models.tag import Tag
from blog.schemas import PostFormInput, PostUpdate, normalise_tags
from blog.schemas.post import PostForm, PostResponse
from blog.schemas.user import UserPublic


# --- PostForm: tag defaults ---------------------------------------------
def test_post_form_default_empty_tags():
    post = PostForm(title="my title", summary="a summary", content="body text")

    assert post.tags == []


def test_post_form_different_default_tags():
    first = PostForm(title="t", summary="s", content="c")
    second = PostForm(title="t", summary="s", content="c")

    assert first.tags is not second.tags


# --- PostForm: title, summary, content length boundaries ----------------
@pytest.mark.parametrize(
    "field, max_length",
    [
        ("title", 100),
        ("summary", 250),
    ],
    ids=["title", "summary"],
)
def test_post_form_at_max_length_accepted(field, max_length):
    values: dict[str, str] = {"title": "t", "summary": "s", "content": "c"}
    values[field] = "x" * max_length

    post = PostForm(**values)

    assert len(getattr(post, field)) == max_length


@pytest.mark.parametrize(
    "field, max_length",
    [
        ("title", 100),
        ("summary", 250),
    ],
    ids=["title", "summary"],
)
def test_post_form_over_max_length_error(field, max_length):
    values: dict[str, str] = {"title": "t", "summary": "s", "content": "c"}
    values[field] = "x" * (max_length + 1)

    with pytest.raises(ValidationError) as exc_info:
        PostForm(**values)

    error = exc_info.value.errors()[0]
    assert error["loc"] == (field,)
    assert error["type"] == "string_too_long"


@pytest.mark.parametrize(
    "field", ["title", "summary", "content"], ids=["title", "summary", "content"]
)
def test_post_form_empty_error(field):
    values: dict[str, str] = {"title": "t", "summary": "s", "content": "c"}
    values[field] = ""

    with pytest.raises(ValidationError) as exc_info:
        PostForm(**values)

    error = exc_info.value.errors()[0]
    assert error["loc"] == (field,)
    assert error["type"] == "string_too_short"


@pytest.mark.parametrize(
    "field, min_length",
    [("title", 1), ("summary", 1), ("content", 1)],
    ids=["title", "summary", "content"],
)
def test_post_form_at_min_length_accepted(field, min_length):
    values: dict[str, str] = {"title": "t", "summary": "s", "content": "c"}
    values[field] = "x" * min_length

    post = PostForm(**values)

    assert len(getattr(post, field)) == min_length


# --- PostUpdate: title, summary, content length boundaries ---------------
@pytest.mark.parametrize(
    "field, max_length", [("title", 100), ("summary", 250)], ids=["title", "summary"]
)
def test_post_update_max_length_accepted(field, max_length):
    values = {"title": "t", "summary": "s"}
    values[field] = "x" * max_length

    post = PostUpdate(**values)

    assert len(getattr(post, field)) == max_length


@pytest.mark.parametrize(
    "field, max_length", [("title", 100), ("summary", 250)], ids=["title", "summary"]
)
def test_post_update_over_max_length_error(field, max_length):
    values = {"title": "t", "summary": "s"}
    values[field] = "x" * (max_length + 1)

    with pytest.raises(ValidationError) as exc_info:
        PostUpdate(**values)

    error = exc_info.value.errors()[0]
    assert error["loc"] == (field,)
    assert error["type"] == "string_too_long"


@pytest.mark.parametrize(
    "field, min_length",
    [("title", 1), ("summary", 1), ("content", 1)],
    ids=["title", "summary", "content"],
)
def test_post_update_empty_length_error(field, min_length):
    values = {"title": "t", "summary": "s", "content": "c"}
    values[field] = "x" * (min_length - 1)

    with pytest.raises(ValidationError) as exc_info:
        PostUpdate(**values)

    error = exc_info.value.errors()[0]
    assert error["loc"] == (field,)
    assert error["type"] == "string_too_short"


@pytest.mark.parametrize(
    "field, min_length",
    [("title", 1), ("summary", 1), ("content", 1)],
    ids=["title", "summary", "content"],
)
def test_post_update_min_length_accepted(field, min_length):
    values = {"title": "t", "summary": "s", "content": "c"}
    values[field] = "x" * min_length

    post = PostUpdate(**values)

    assert len(getattr(post, field)) == min_length


# --- PostUpdate: tags -----------------------------------------------------
def test_post_update_with_none_tags():
    post = PostUpdate(title="my title", tags=None)

    assert post.tags is None


def test_post_update_with_normal_tags():
    post = PostUpdate(title="title", tags=["Python", " sql "])

    assert post.tags == ["python", "sql"]


# --- PostFormInput.validated() --------------------------------------------
def test_post_form_input_validation_success():
    post = PostFormInput(title="t", summary="s", content="c", tags="").validated()

    assert post.title == "t"
    assert post.summary == "s"
    assert post.content == "c"


def test_post_form_input_empty_form_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        PostFormInput().validated()

    errors = {(error["loc"], error["type"]) for error in exc_info.value.errors()}
    assert errors == {
        (("title",), "string_too_short"),
        (("summary",), "string_too_short"),
        (("content",), "string_too_short"),
    }


def test_post_form_input_incomplete_form_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        PostFormInput(title="t").validated()

    errors = {(error["loc"], error["type"]) for error in exc_info.value.errors()}
    assert errors == {
        (("summary",), "string_too_short"),
        (("content",), "string_too_short"),
    }


def test_post_form_input_validated_duplicate_string_tags():
    post = PostFormInput(
        title="t", summary="s", content="c", tags="python, sql, python"
    ).validated()

    assert post.tags == ["python", "sql"]


def test_post_form_input_validated_empty_string_tags():
    post = PostFormInput(title="t", summary="s", content="c", tags="").validated()

    assert post.tags == []


def test_post_form_input_validated_middle_empty_tag():
    post = PostFormInput(title="t", summary="s", content="c", tags="python,, sql").validated()

    assert post.tags == ["python", "sql"]


# --- normalise_tags --------------------------------------------------------
def test_normalise_tags_strips_and_lowercases():
    assert normalise_tags(["Python", " SQL "]) == ["python", "sql"]


def test_normalise_tags_drops_empty_entries():
    assert normalise_tags(["", "  ", "python"]) == ["python"]


def test_normalise_tags_deduplicates():
    assert normalise_tags(["b", "a", "b"]) == ["b", "a"]


def test_normalise_tags_empty_input():
    assert normalise_tags([]) == []


# --- PostResponse.flatten_tags ---------------------------------------------
def test_post_response_flatten_tags_plain_strings():
    post = PostResponse(
        id=1,
        author=UserPublic(id=1, username="u", image_file=None, image_path="/x"),
        title="t",
        summary="s",
        date_posted=datetime.now(tz=UTC),
        is_pinned=False,
        tags=["python", "sql"],
        reading_minutes=1,
    )

    assert post.tags == ["python", "sql"]


def test_post_response_flatten_tags_objects():
    post = PostResponse(
        id=1,
        author=UserPublic(id=1, username="u", image_file=None, image_path="/x"),
        title="t",
        summary="s",
        date_posted=datetime.now(tz=UTC),
        is_pinned=False,
        tags=[Tag(name="python"), Tag(name="sql")],
        reading_minutes=1,
    )

    assert post.tags == ["python", "sql"]


def test_post_response_flatten_tags_empty_list():
    post = PostResponse(
        id=1,
        author=UserPublic(id=1, username="u", image_file=None, image_path="/x"),
        title="t",
        summary="s",
        date_posted=datetime.now(tz=UTC),
        is_pinned=False,
        tags=[],
        reading_minutes=1,
    )

    assert post.tags == []
