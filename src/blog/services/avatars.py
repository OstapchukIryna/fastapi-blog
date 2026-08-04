"""Profile pictures: the rules about them, and where they are kept.

Split out of services/users.py, which described itself as "registration,
login, profile and picture management" — four subjects in one docstring is
the usual sign. A picture has nothing in common with a username: what can
go wrong is that the bytes are too many or are not an image, and what has
to be got right is that the old file disappears only once the new name is
committed.

This module does not know where a picture is kept. It states what it needs
— store these bytes, drop that filename — and is handed something that can
do it.

! A Protocol, not an abstract base class. An ABC would have to be
! inherited, so infrastructure/images.py would have to import this module:
! an arrow from a lower layer to a higher one, which is exactly what
! tests/test_import_graph.py refuses. A Protocol is satisfied by shape, so
! DiskAvatars matches it without ever hearing about it — the dependency
! is inverted and the import graph stays pointing down.
"""

from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, UploadFile, status
from PIL import UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from blog.core.config import settings
from blog.infrastructure import models
from blog.infrastructure.images import DiskAvatars


class AvatarStorage(Protocol):
    """Somewhere profile pictures can be kept.

    Two methods, because two is what this service uses. A wider interface
    — read one back, list them, work out a URL — would be a promise every
    future implementation has to keep in order to serve callers that do
    not exist.

    ! Each body is a docstring and nothing else. `...` would be a
    ! statement, and a statement in a body that never runs is a line
    ! coverage reports as missed for as long as the protocol exists. A
    ! docstring is not a statement, so there is nothing left to miss —
    ! and the method is documented, which `...` never was.
    """

    def save(self, content: bytes) -> str:
        """Store these bytes as an avatar and return the name to keep.

        Args:
            content (bytes): the uploaded file, already in memory. The size
                ceiling has been applied by the time this is called.

        Returns:
            str: the stored name, to go on the user row. A name and not a
                path: where a picture lives is the implementation's
                business, and the database should not learn it.

        Raises:
            PIL.UnidentifiedImageError: the bytes are not an image.
        """

    def delete(self, filename: str | None) -> None:
        """Remove a stored avatar, if there is one.

        Accepts None and a name that is no longer there, so a caller can
        say "drop whatever this user had" without asking first.

        Args:
            filename (str | None): the stored name, or None when there
                never was a picture.
        """


def get_avatar_storage() -> AvatarStorage:
    """Hand out the storage this application actually runs on.

    The one place a concrete implementation is named. Everything else —
    this module, the routes, the account service that deletes a picture
    with its account — is typed against the protocol, so moving avatars
    to object storage is a change to this function and to nothing else.

    It is also how a test avoids the disk: `app.dependency_overrides` on
    this function, and no route has to be told.

    Returns:
        AvatarStorage: files in the directory /media is served from.
    """
    return DiskAvatars()


# ! Must exist at runtime — FastAPI reads annotations to resolve
# ! dependencies. See the note on DbSession in infrastructure/database.py.
AvatarStore = Annotated[AvatarStorage, Depends(get_avatar_storage)]


class UploadTooLarge(HTTPException):
    """The 400 for an upload over the configured ceiling.

    Checked on the raw bytes, before Pillow is asked to decode them: a
    decoder is the wrong place to discover that somebody sent a gigabyte.
    """

    def __init__(self) -> None:
        """Build the refusal, naming the limit in megabytes."""
        megabytes = settings.max_upload_size_bytes // (1024 * 1024)
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is too large. Maximum size is {megabytes} MB",
        )


class NotAnImage(HTTPException):
    """The 400 for bytes Pillow does not recognise.

    The message lists formats rather than repeating "invalid", because the
    person reading it is choosing another file and that is the decision
    they have to make.
    """

    def __init__(self) -> None:
        """Build the refusal."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid image file. Please upload a valid file format "
                "(JPEG, PNG, GIF, WebP)."
            ),
        )


class NoPicture(HTTPException):
    """The 400 for removing a picture that is not there.

    400 rather than 404: the account exists and the address is right. What
    is wrong is that the request asks for something already true.
    """

    def __init__(self) -> None:
        """Build the refusal."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No picture to delete.",
        )


async def set_picture(
    db: AsyncSession,
    user: models.User,
    file: UploadFile,
    storage: AvatarStorage,
) -> models.User:
    """Replace this user's profile picture, and drop the file it replaces.

    The old file goes last, after the commit. Deleting it first would mean
    a failed transaction leaves a row pointing at a filename that no
    longer exists — a profile with a broken picture and no way back.

    Args:
        db (AsyncSession): session to write through.
        user (models.User): the account, already established as the
            caller's by the dependency.
        file (UploadFile): the upload, in whatever format arrived.
        storage (AvatarStorage): where to put it and what to remove from.

    Returns:
        models.User: the account, with the new filename on it.

    Raises:
        UploadTooLarge: the upload is over the size ceiling.
        NotAnImage: the bytes are not something Pillow can read.
    """
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise UploadTooLarge()

    try:
        # * Storing is synchronous and not free — decoding and resampling
        # * are CPU-bound — so it runs in a worker thread rather than
        # * holding up the event loop for every other request.
        new_filename = await run_in_threadpool(storage.save, content)
    except UnidentifiedImageError as err:
        # * The cause is kept, unlike the refusals that guard a race: what
        # * Pillow objected to is useful in a log and gives nothing away.
        raise NotAnImage() from err

    old_filename = user.image_file
    user.image_file = new_filename
    await db.commit()
    await db.refresh(user)

    storage.delete(old_filename)
    return user


async def remove_picture(
    db: AsyncSession, user: models.User, storage: AvatarStorage
) -> models.User:
    """Back to the shared default, and the uploaded file goes.

    Args:
        db (AsyncSession): session to write through.
        user (models.User): the account, already established as the
            caller's by the dependency.
        storage (AvatarStorage): where the file being removed lives.

    Returns:
        models.User: the account, now pointing at the default avatar
            through its image_path property.

    Raises:
        NoPicture: there was nothing to remove.
    """
    old_filename = user.image_file
    if old_filename is None:
        raise NoPicture()

    user.image_file = None
    await db.commit()
    await db.refresh(user)

    storage.delete(old_filename)
    return user
