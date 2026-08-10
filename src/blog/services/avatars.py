"""All about profile pictures. Setting up, replace and remove avatars.

Also holding all the errors that can be raised while processing an image.

Storage in AWS S3 only.
"""

import logging
from typing import Annotated

from botocore.exceptions import ClientError
from fastapi import Depends, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from blog.core.config import settings
from blog.core.errors import AppHTTPError
from blog.infrastructure import models
from blog.infrastructure.images import AWSAvatars

AvatarStore = Annotated[AWSAvatars, Depends(AWSAvatars)]

# * Read in chunks, not file.read() then check len(): a whole gigabyte
# * behind a 5 MB configured limit is fully in memory by the time a
# * single-shot read gets around to measuring it, no matter what the
# * limit says - and several such uploads at once are what actually
# * bring a process down, not the one that trips the check. This size is
# * a compromise, not a tuned value: small enough that the last chunk
# * before the limit rejects a request does not itself blow the budget
# * by much, large enough that a real photo does not take thousands of
# * calls to read.
_UPLOAD_READ_CHUNK_SIZE = 1024 * 1024


class UploadTooLarge(AppHTTPError):
    """The 400 for an upload past the configured size ceiling."""

    def __init__(self) -> None:
        """Build the refusal, with the actual ceiling in the message."""
        megabytes = settings.max_upload_size_bytes // (1024 * 1024)
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is too large. Maximum size is {megabytes} MB",
        )


class NotAnImage(AppHTTPError):
    """The 400 for an upload Pillow could not identify as an image."""

    def __init__(self) -> None:
        """Build the refusal."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid image file. Please upload a valid file format (JPEG, PNG, GIF, WebP)."
            ),
        )


class NoPicture(AppHTTPError):
    """The 400 for removing a picture the account does not have."""

    def __init__(self) -> None:
        """Build the refusal."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No picture to delete.",
        )


class FailedUpload(AppHTTPError):
    """The 500 for a storage failure partway through an upload."""

    def __init__(self) -> None:
        """Build the refusal."""
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload an image. Please try again",
        )


logger = logging.getLogger(__name__)


async def _read_within_limit(file: UploadFile, limit: int) -> bytes:
    """Read an upload without ever holding more than limit (plus one chunk) of it.

    Args:
        file (UploadFile): the upload, not yet read.
        limit (int): the configured ceiling in bytes.

    Returns:
        bytes: the whole upload, once it is confirmed to fit.

    Raises:
        UploadTooLarge: the upload exceeds limit. Raised as soon as that
            is known, not after reading the rest of it to find out.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise UploadTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


async def set_picture(
    db: AsyncSession,
    user: models.User,
    file: UploadFile,
    storage: AWSAvatars,
) -> models.User:
    """Replace the caller's profile picture, and drop the one it replaces.

    Args:
        db (AsyncSession): session to write through.
        user (models.User): the account whose picture is changing.
        file (UploadFile): the upload, not yet read.
        storage (AWSAvatars): where the picture is kept.

    Returns:
        models.User: the account, with image_file already pointing at
            the new picture.

    Raises:
        UploadTooLarge: the upload exceeds max_upload_size_bytes.
        NotAnImage: Pillow could not decode the upload as an image, or
            refused it as an oversized decompression bomb.
        FailedUpload: the resized image could not be stored.
    """
    content = await _read_within_limit(file, settings.max_upload_size_bytes)

    try:
        file_bytes, new_filename = await run_in_threadpool(storage.process_profile_image, content)
    except (UnidentifiedImageError, Image.DecompressionBombError) as err:
        raise NotAnImage() from err

    try:
        await storage.upload_profile_image(file_bytes, new_filename)
    except ClientError as err:
        raise FailedUpload() from err

    old_filename = user.image_file
    user.image_file = new_filename
    await db.commit()

    # * Not a failure of this request: the database is already correct,
    # * and there is nothing left pointing at the old file for a caller
    # * to be told about. Logged so an S3 outage that strands a file is
    # * at least visible after the fact, the same trade as on account
    # * deletion in services/users.py.
    try:
        await storage.delete_profile_picture(old_filename)
    except ClientError:
        logger.exception("orphaned avatar %r: replaced but not removed from storage", old_filename)

    return user


async def remove_picture(db: AsyncSession, user: models.User, storage: AWSAvatars) -> models.User:
    """Drop the caller's profile picture, back to the shared default.

    Args:
        db (AsyncSession): session to write through.
        user (models.User): the account losing its picture.
        storage (AWSAvatars): where the picture is kept.

    Returns:
        models.User: the account, with image_file already None.

    Raises:
        NoPicture: the account had no picture of its own to remove.
    """
    old_filename = user.image_file
    if old_filename is None:
        raise NoPicture()

    user.image_file = None
    await db.commit()

    try:
        await storage.delete_profile_picture(old_filename)
    except ClientError:
        logger.exception("orphaned avatar %r: cleared but not removed from storage", old_filename)

    return user
