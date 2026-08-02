import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from blog.core.config import MEDIA_DIR

PROFILE_PICS_DIR: Path = MEDIA_DIR / "profile_pics"


def process_profile_image(content: bytes) -> str:
    with Image.open(BytesIO(content)) as orig:
        img = ImageOps.exif_transpose(orig)
        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        filename = f"{uuid.uuid4().hex}.jpg"
        filepath = PROFILE_PICS_DIR / filename

        PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)

        img.save(filepath, "JPEG", quality=85, optimize=True)
    return filename


def delete_profile_image(filename: str | None) -> None:
    if filename is None:
        return

    filepath = PROFILE_PICS_DIR / filename
    if filepath.exists():
        filepath.unlink()
