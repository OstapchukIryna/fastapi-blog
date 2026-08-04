"""Profile pictures on disk: turn an upload into a file, and remove it later.

Uploads are normalised rather than stored as they arrive. Everything that
reaches the disk is a square JPEG of a known size, so the pages never
have to cope with a 12-megapixel portrait or a transparent PNG.

The two operations are methods on an object rather than two module
functions, for one reason: the directory becomes a field. Production
takes the default, a test points it at tmp_path, and the service that
saves pictures is handed the object instead of importing it.

What that object has to look like is written down one layer up, as
`AvatarStorage` in services/avatars.py — next to the code that needs it.
Nothing here imports that protocol, and nothing here has to: a Protocol
is satisfied by shape. That is what keeps this file at the bottom of the
graph while the decision about what storage *means* stays with its user.
"""

import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from blog.core.config import MEDIA_DIR

PROFILE_PICS_DIR: Path = MEDIA_DIR / "profile_pics"

AVATAR_SIZE = (300, 300)
JPEG_QUALITY = 85


@dataclass(frozen=True, slots=True)
class DiskAvatars:
    """Avatars kept as JPEG files in one directory.

    Frozen, and holding nothing but the directory: two instances pointing
    at the same place are interchangeable, there is no state to fall out
    of step between requests, and building a fresh one per request costs
    nothing.

    Attributes:
        directory (Path): where the files go. Defaults to the directory
            /media is served from, so the application needs no argument;
            a test points it somewhere temporary and leaves no litter in
            the repository.
    """

    directory: Path = PROFILE_PICS_DIR

    def save(self, content: bytes) -> str:
        """Store an uploaded image as a square avatar and return its filename.

        Blocking work: decoding and resampling are CPU-bound and Pillow is
        synchronous, so callers run this in a worker thread rather than on
        the event loop.

        Args:
            content (bytes): the uploaded file, already read into memory.
                The size ceiling is applied before this is called.

        Returns:
            str: the generated filename, to be stored on the user row. Only
                the name, not the path — where the directory lives is this
                object's business, not the database's.

        Raises:
            PIL.UnidentifiedImageError: the bytes are not an image Pillow
                recognises. The caller turns this into a 400.
        """
        with Image.open(BytesIO(content)) as original:
            # * Phone cameras record orientation as a flag rather than
            # * rotating the pixels. Without this, portraits arrive sideways.
            image = ImageOps.exif_transpose(original)

            # * fit() crops to the aspect ratio before scaling, so faces stay
            # * proportioned. resize() alone would squash a tall photo.
            image = ImageOps.fit(image, AVATAR_SIZE, method=Image.Resampling.LANCZOS)

            # ! JPEG has no alpha channel; saving a transparent image as one
            # ! raises rather than flattening it.
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGB")

            # * A fresh random name per upload. Naming the file after the user
            # * would leave browsers and CDNs serving the previous picture from
            # * cache after a change, and a name taken from the upload could
            # * collide or contain path separators.
            filename = f"{uuid.uuid4().hex}.jpg"

            # media/ is not in the repository, so on a fresh clone the
            # directory may not exist yet.
            self.directory.mkdir(parents=True, exist_ok=True)
            image.save(
                self.directory / filename, "JPEG", quality=JPEG_QUALITY, optimize=True
            )

        return filename

    def delete(self, filename: str | None) -> None:
        """Remove a stored avatar, if there is one.

        Accepts None and a name that no longer exists on disk, so callers
        can say "drop whatever this user had" without first checking
        whether they had anything. Deleting a picture is always the last
        step after a successful commit: if the transaction fails, the old
        file must still be there.

        Args:
            filename (str | None): the stored filename, or None when the
                user never uploaded one.
        """
        if filename is None:
            return

        filepath = self.directory / filename
        if filepath.exists():
            filepath.unlink()
