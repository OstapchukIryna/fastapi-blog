from io import BytesIO

import pytest
from PIL import Image

from blog.infrastructure.images import AVATAR_SIZE, AWSAvatars
from tests.conftest import S3_BUCKET_NAME


# --- AWSAvatars.process_profile_image ---------------------------------------
def test_process_profile_image_converts_rgba_to_rgb():
    buffer = BytesIO()
    Image.new("RGBA", (500, 500), (255, 0, 0, 128)).save(buffer, "PNG")

    file_bytes, filename = AWSAvatars().process_profile_image(buffer.getvalue())

    assert filename.endswith(".jpg")
    with Image.open(BytesIO(file_bytes)) as result:
        assert result.mode == "RGB"
        assert result.size == AVATAR_SIZE


# --- AWSAvatars.clear_profile_pictures --------------------------------------
@pytest.mark.anyio
async def test_clear_profile_pictures_empties_the_prefix(mocked_aws):
    mocked_aws.put_object(Bucket=S3_BUCKET_NAME, Key="profile_pics/one.jpg", Body=b"x")
    mocked_aws.put_object(Bucket=S3_BUCKET_NAME, Key="profile_pics/two.jpg", Body=b"x")

    await AWSAvatars().clear_profile_pictures()

    result = mocked_aws.list_objects_v2(Bucket=S3_BUCKET_NAME)
    assert "Contents" not in result


@pytest.mark.anyio
async def test_clear_profile_pictures_nothing_to_clear(mocked_aws):
    # must not raise when the prefix is already empty
    await AWSAvatars().clear_profile_pictures()

    result = mocked_aws.list_objects_v2(Bucket=S3_BUCKET_NAME)
    assert "Contents" not in result
