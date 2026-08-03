"""Accounts as they cross the boundary: what may be sent in, what goes out.

Two response models rather than one with a flag. `UserPublic` is what
anybody may see; `UserPrivate` adds the email and is returned only to the
account's owner. Which fields leave the application is decided by the
class the route names, so the separation is enforced by the response
model rather than by remembering to filter.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Fields every account has and a caller may set.

    Attributes:
        username (str): public handle.
        email (EmailStr): validated for shape only. Nobody sends mail to
            it yet, so no confirmation step exists.
    """

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr = Field(min_length=3, max_length=120)


class UserCreate(UserBase):
    """Registration.

    Attributes:
        password (str): the password as typed. The lower bound is a
            weak guard, not a policy; the upper bound exists because a
            multi-megabyte password is a way to make the server spend a
            long time hashing.
    """

    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """A partial change to an account, for PATCH.

    Every field optional, and None means "not sent". The same constraints
    still apply to whatever is sent: only the requirement to send the
    field at all is lifted.

    Attributes:
        username (str | None): new handle, if changing it.
        email (EmailStr | None): new address, if changing it.
        password (str | None): new password, if changing it. Hashed
            before it reaches the model — it is never stored as typed.
    """

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = Field(default=None, min_length=3, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserPublic(BaseModel):
    """An account as anybody may see it.

    Attributes:
        id (int): the account's id.
        username (str): public handle.
        image_file (str | None): stored avatar filename, or None.
        image_path (str): where to fetch the avatar, default included.
            Read from the model's property, so a client never has to know
            how the default is chosen.
    """

    # * Lets the model be built straight from an ORM object, which is
    # * what allows services to return rows and routes to declare a
    # * response model without a conversion step in between.
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    image_file: str | None
    image_path: str


class UserPrivate(UserPublic):
    """An account as its owner sees it: everything public, plus the email.

    Attributes:
        email (EmailStr): the address on the account. Returned only from
            endpoints that have already established who is asking.
    """

    model_config = ConfigDict(from_attributes=True)

    email: EmailStr


class Token(BaseModel):
    """What a successful sign-in returns.

    Attributes:
        access_token (str): the signed JWT.
        token_type (str): always "bearer"; the field exists because the
            OAuth2 password flow specifies it, and clients read it to
            build the Authorization header.
    """

    access_token: str
    token_type: str
