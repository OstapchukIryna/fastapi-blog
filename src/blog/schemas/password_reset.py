"""What the password endpoints accept and answer.

Three requests rather than one, because they happen in three different
situations and carry different proof: an address alone, a token from an
email, or the current password from somebody already signed in.
"""

from pydantic import BaseModel, EmailStr, Field

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class ForgotPasswordRequest(BaseModel):
    """ "I cannot sign in, send me a link."

    Attributes:
        email (EmailStr): where to send it. Whether anybody holds this
            address is never revealed by the response.
    """

    email: EmailStr = Field(max_length=120)


class ResetPasswordRequest(BaseModel):
    """The link has been opened; here is the new password.

    Attributes:
        token (str): the one-time token from the email.
        new_password (str): the replacement. Bounded at both ends for the
            same reasons as registration — a floor that is a weak guard,
            and a ceiling so a huge value cannot make the server spend a
            long time hashing.
    """

    token: str
    new_password: str = Field(
        min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )


class ChangePasswordRequest(BaseModel):
    """A signed-in person changing their own password.

    Attributes:
        current_password (str): proof that whoever holds this session
            also knows the password. Unbounded on purpose — it is checked
            against a hash, not stored, and a length rule here would leak
            the shape of the real one.
        new_password (str): the replacement.
    """

    current_password: str
    new_password: str = Field(
        min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )


class Message(BaseModel):
    """A one-sentence outcome, for endpoints that return no resource.

    A model rather than a bare dict so the sentence appears in
    /openapi.json and a client can rely on the key being there.

    Attributes:
        message (str): what happened, in words meant for a person.
    """

    message: str
