"""Profile pictures on S3: turn an upload into a stored object, and remove
it later.

Uploads are normalised rather than stored as they arrive. Everything that
reaches the bucket is a square JPEG of a known size, so the pages never
have to cope with a 12-megapixel portrait or a transparent PNG.

The three steps are separate methods, not one, because two of them are
about the bytes (decode, resize, encode — CPU-bound, no network) and one
is about the network (upload to S3 — no CPU work of its own). Keeping
them apart is what lets `services/avatars.py` run the first in a worker
thread and await the second directly, instead of blocking the event loop
for a request that is mostly waiting on S3.

This is the only storage the application uses, and no other is planned,
so `AWSAvatars` is used directly by `services/avatars.py` — no protocol
standing between them.
"""

import uuid
from dataclasses import dataclass
from io import BytesIO

import boto3
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from blog.core.config import settings

# * Pillow's own default (~89 megapixels) only warns up to double that
# * and raises DecompressionBombError past it — so a file just inside the
# * upload size cap but built to decode into, say, 100 megapixels would
# * sail through as a warning, not a refusal, and this process would
# * still have to allocate the bitmap. Lowering the ceiling here brings
# * the raise threshold down with it (Pillow's is always 2x this value).
# * 40 megapixels is generous for what this module ever does with the
# * result — everything gets cropped to AVATAR_SIZE regardless of how
# * large it arrived — so nothing legitimate is refused, and anything
# * built to be a bomb hits DecompressionBombError, which
# * services/avatars.py already turns into a 400.
Image.MAX_IMAGE_PIXELS = 40_000_000

AVATAR_SIZE = (300, 300)
JPEG_QUALITY = 85


# AWS helper functions
def _get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=(
            settings.s3_access_key_id.get_secret_value() if settings.s3_access_key_id else None
        ),
        aws_secret_access_key=(
            settings.s3_secret_access_key.get_secret_value()
            if settings.s3_secret_access_key
            else None
        ),
        endpoint_url=settings.s3_endpoint_url,
    )


def _upload_to_s3(file_bytes: bytes, key: str) -> None:
    s3 = _get_s3_client()
    s3.upload_fileobj(
        BytesIO(file_bytes),
        settings.s3_bucket_name,
        key,
        ExtraArgs={"ContentType": "image/jpeg"},
    )


def _delete_from_s3(key: str) -> None:
    s3 = _get_s3_client()
    s3.delete_object(Bucket=settings.s3_bucket_name, Key=key)


@dataclass(frozen=True, slots=True)
class AWSAvatars:
    """Avatars kept as JPEG objects in one S3 bucket.

    Holds no state of its own — the bucket and credentials come from
    `settings` — so every instance is interchangeable and building a
    fresh one per request costs nothing.
    """

    def process_profile_image(self, content: bytes) -> tuple[bytes, str]:
        """Turn an upload into a square JPEG and a name to store it under.

        Blocking work: decoding and resampling are CPU-bound and Pillow is
        synchronous, so callers run this in a worker thread rather than on
        the event loop.

        Args:
            content (bytes): the uploaded file, already read into memory.
                The size ceiling is applied before this is called.

        Returns:
            tuple[bytes, str]: the encoded JPEG, ready for
                `upload_profile_image`, and the filename generated for it —
                only the name, not a path, since where it ends up living is
                this object's business, not the database's.

        Raises:
            PIL.UnidentifiedImageError: the bytes are not an image Pillow
                recognises. The caller turns this into a 400.
        """
        with Image.open(BytesIO(content)) as original:
            image = ImageOps.exif_transpose(original)

            # fit() crops to the aspect ratio before scaling
            image = ImageOps.fit(image, AVATAR_SIZE, method=Image.Resampling.LANCZOS)

            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGB")

            filename = f"{uuid.uuid4().hex}.jpg"
            output = BytesIO()

            image.save(output, "JPEG", quality=JPEG_QUALITY, optimize=True)
            output.seek(0)

        return output.read(), filename

    async def upload_profile_image(self, file_bytes: bytes, filename: str) -> None:
        """Put the encoded JPEG from `process_profile_image` into the bucket.

        Args:
            file_bytes (bytes): the encoded JPEG.
            filename (str): the name generated for it.
        """
        key = f"profile_pics/{filename}"
        await run_in_threadpool(_upload_to_s3, file_bytes, key)

    async def delete_profile_picture(self, filename: str | None) -> None:
        """Remove a stored avatar, if there is one.

        Accepts None and a name that is no longer there, so a caller can
        say "drop whatever this user had" without asking first.

        Args:
            filename (str | None): the stored name, or None when there
                never was a picture.
        """
        if filename is None:
            return
        key = f"profile_pics/{filename}"
        await run_in_threadpool(_delete_from_s3, key)

    def avatar_url(self, filename: str) -> str:
        """The URL a stored avatar is reachable at.

        Path-style when s3_endpoint_url is set, not virtual-hosted: a
        custom endpoint means a non-AWS S3-compatible provider — Linode
        Object Storage or a local MinIO, the two this setting exists
        for — and path-style is the one addressing scheme every one of
        them accepts, where virtual-hosted subdomains are not guaranteed
        to resolve. Falls back to AWS's own virtual-hosted URL when no
        endpoint override is configured, which is the ordinary case.

        Args:
            filename (str): the stored name, as kept in `image_file`.

        Returns:
            str: the full URL to fetch the image from.
        """
        key = f"profile_pics/{filename}"
        if settings.s3_endpoint_url:
            return f"{settings.s3_endpoint_url}/{settings.s3_bucket_name}/{key}"
        return f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com/{key}"
