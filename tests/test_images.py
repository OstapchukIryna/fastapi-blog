from io import BytesIO

from PIL import Image

from blog.core.config import settings
from blog.infrastructure.images import AVATAR_SIZE, AWSAvatars


# --- AWSAvatars.process_profile_image ---------------------------------------
def test_process_profile_image_converts_rgba_to_rgb():
    buffer = BytesIO()
    Image.new("RGBA", (500, 500), (255, 0, 0, 128)).save(buffer, "PNG")

    file_bytes, filename = AWSAvatars().process_profile_image(buffer.getvalue())

    assert filename.endswith(".jpg")
    with Image.open(BytesIO(file_bytes)) as result:
        assert result.mode == "RGB"
        assert result.size == AVATAR_SIZE


# --- AWSAvatars.avatar_url ---------------------------------------------------
def test_avatar_url_without_endpoint_override_uses_aws_virtual_hosted_style():
    assert settings.s3_endpoint_url is None  # the untouched default this test relies on

    url = AWSAvatars().avatar_url("abc123.jpg")

    assert url == (
        f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com"
        "/profile_pics/abc123.jpg"
    )


def test_avatar_url_with_endpoint_override_uses_path_style(monkeypatch):
    # Linode Object Storage or a local MinIO - the two reasons
    # s3_endpoint_url exists at all - are reached through a URL of their
    # own, not amazonaws.com, and not every such endpoint resolves a
    # bucket subdomain the way AWS's own does.
    monkeypatch.setattr(settings, "s3_endpoint_url", "https://us-east-1.linodeobjects.com")

    url = AWSAvatars().avatar_url("abc123.jpg")

    assert url == (
        f"https://us-east-1.linodeobjects.com/{settings.s3_bucket_name}/profile_pics/abc123.jpg"
    )
