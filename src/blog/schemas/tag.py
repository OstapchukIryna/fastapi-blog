from pydantic import BaseModel


class TagCount(BaseModel):
    name: str
    count: int


def normalise_tags(value: list[str]) -> list[str]:
    """
    Strip, lowercase and de-duplicate a list of tag names.

    Shared by every schema that accepts tags, so the rules cannot drift
    apart between creating and updating a post.

    Lives in the schema layer rather than in services because it is pure
    data cleaning: no session, no request, nothing a service owns. It sat
    in the tags router once, and since that router imports schemas back
    by way of the posts one, importing the application failed on a
    partially initialised module.

    Args:
        value (list[str]): tag names as received.

    Returns:
        list[str]: cleaned names, blanks dropped, order preserved.

    """
    cleaned = [tag.strip().lower() for tag in value if tag.strip()]
    # dict keeps order
    return list(dict.fromkeys(cleaned))
