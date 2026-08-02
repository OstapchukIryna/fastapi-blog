from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr = Field(min_length=3, max_length=120)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = Field(default=None, min_length=3, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    image_file: str | None
    image_path: str


class UserPrivate(UserPublic):
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str
