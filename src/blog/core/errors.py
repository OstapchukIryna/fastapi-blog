"""The shared vocabulary for a deliberate refusal.

Everything here is still an `HTTPException` on purpose: `presentation/errors.py`
already dispatches on that exact class, and staying inside it means a new
refusal costs one subclass, not a second handler to register and keep in
sync with the first. The usual alternative — clean domain exceptions,
mapped to HTTP by a second layer — is more code for a separation this
application has no consumer that needs yet.

The price of that choice: services now depend on HTTP by inheritance, not
just by the status codes they choose. A CLI or a queue consumer added
later would find itself catching HTTPException, a concept it has nothing
to do with. Worth paying now; worth undoing the day a non-HTTP caller
actually shows up, not before.

The 401 in this family, `Unauthorized`, is not in this file — it lives in
core/security.py, next to the JWT functions that need the
WWW-Authenticate challenge header it carries. Look there for it, not here.
"""

from fastapi import HTTPException, status


class AppHTTPError(HTTPException):
    """Base for every refusal this application raises on purpose.

    Carries no behaviour of its own — status, message and headers are
    each subclass's job. What it buys is one name a caller, a test, or a
    future logging hook can catch instead of naming all of them.
    """


class NotFound(AppHTTPError):
    """The 404 for a resource that does not exist at this id."""

    def __init__(self, resource: str) -> None:
        """Build the refusal.

        Args:
            resource (str): what was being looked up, capitalised as it
                should read to a caller — becomes "`{resource}` not found".
                A convention, not a checked contract: `NotFound("post")`
                builds without complaint and reads wrong in the response.
        """
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found")


class Forbidden(AppHTTPError):
    """The 403 for a caller who is known but not entitled to this."""

    def __init__(self, detail: str) -> None:
        """Build the refusal.

        Args:
            detail (str): what the caller is told they may not do.
        """
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
