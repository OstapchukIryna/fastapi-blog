"""All about profile pictures. Setting up, replace and remove avatars.

Also holding all the errors can be raised with image proccessing.

Storage in AWS S3 only.
"""

from typing import Annotated

from botocore.exceptions import ClientError
from fastapi import Depends, HTTPException, UploadFile, status
from PIL import UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from blog.core.config import settings
from blog.infrastructure import models
from blog.infrastructure.images import AWSAvatars

AvatarStore = Annotated[AWSAvatars, Depends(AWSAvatars)]


class UploadTooLarge(HTTPException):
    def __init__(self) -> None:
        megabytes = settings.max_upload_size_bytes // (1024 * 1024)
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is too large. Maximum size is {megabytes} MB",
        )


class NotAnImage(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid image file. Please upload a valid file format "
                "(JPEG, PNG, GIF, WebP)."
            ),
        )


class NoPicture(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No picture to delete.",
        )


class FailedUpload(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload an image. Please try again",
        )


async def set_picture(
    db: AsyncSession,
    user: models.User,
    file: UploadFile,
    storage: AWSAvatars,
) -> models.User:
    """Replace current user's profile picture and drop the file it replaces in S3."""

    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise UploadTooLarge()

    try:
        file_bytes, new_filename = await run_in_threadpool(
            storage.process_profile_image, content
        )
    except UnidentifiedImageError as err:
        raise NotAnImage() from err

    # Upload to S3 (also runs in threadpool via async wrapper)
    try:
        await storage.upload_profile_image(file_bytes, new_filename)
    except ClientError as err:
        raise FailedUpload() from err

    old_filename = user.image_file
    user.image_file = new_filename
    await db.commit()
    await db.refresh(user)

    await storage.delete_profile_picture(old_filename)
    return user


async def remove_picture(
    db: AsyncSession, user: models.User, storage: AWSAvatars
) -> models.User:
    """Set default picture and delete the previous one."""
    old_filename = user.image_file
    if old_filename is None:
        raise NoPicture()

    user.image_file = None
    await db.commit()
    await db.refresh(user)

    await storage.delete_profile_picture(old_filename)
    return user
