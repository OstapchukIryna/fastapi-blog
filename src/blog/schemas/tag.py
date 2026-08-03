"""Tags as they appear in responses, and the one rule they all obey."""

from pydantic import BaseModel


class TagCount(BaseModel):
    """A tag and how many posts carry it.

    Attributes:
        name (str): the tag.
        count (int): posts using it. Always at least one — the query
            counts through posts, so a tag nothing references does not
            appear at all.
    """

    name: str
    count: int


def normalise_tags(value: list[str]) -> list[str]:
    """Strip, lower-case and de-duplicate tag names.

    Shared by every schema that accepts tags, so the rules cannot drift
    apart between creating a post and editing one.

    It lives in the schema layer rather than in services because it is
    pure data cleaning: no session, no request, nothing a service owns.
    It sat in the tags router once, and since that router imported
    schemas back by way of the posts one, importing the application
    failed on a partially initialised module.

    Args:
        value (list[str]): tag names as received.

    Returns:
        list[str]: cleaned names with blanks dropped, in the order the
            author typed them — that order is their emphasis, and
            sorting would be a decision nobody asked for.
    """
    cleaned = [tag.strip().lower() for tag in value if tag.strip()]
    # * dict.fromkeys de-duplicates and keeps insertion order; a set
    # * would be shorter and would throw the order away.
    return list(dict.fromkeys(cleaned))
