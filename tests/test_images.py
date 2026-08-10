from io import BytesIO

from PIL import Image

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
