import pytest

from blog.services import avatars


class _HugeVirtualFile:
    """A stand-in for an upload that would be gigabytes if fully read.

    read() only ever produces real, small chunks - the virtual_total is
    never actually allocated. If _read_within_limit ever kept reading
    past the point where it should have raised, max_bytes_returned would
    grow past the limit; if it stops early, as it should, this stays
    small no matter how large virtual_total claims to be.
    """

    def __init__(self, chunk_size: int, virtual_total: int):
        self._chunk_size = chunk_size
        self._remaining = virtual_total
        self.max_bytes_returned = 0

    async def read(self, size: int) -> bytes:
        if self._remaining <= 0:
            return b""
        n = min(size, self._chunk_size, self._remaining)
        self._remaining -= n
        self.max_bytes_returned += n
        return b"x" * n


# --- avatars._read_within_limit ----------------------------------------------
@pytest.mark.anyio
async def test_read_within_limit_stops_before_reading_the_whole_upload():
    ten_gigabytes = 10 * 1024 * 1024 * 1024
    fake = _HugeVirtualFile(chunk_size=avatars._UPLOAD_READ_CHUNK_SIZE, virtual_total=ten_gigabytes)
    limit = 5 * 1024 * 1024

    with pytest.raises(avatars.UploadTooLarge):
        # pyrefly: ignore [bad-argument-type]  # duck-typed stand-in, not a real UploadFile
        await avatars._read_within_limit(fake, limit)

    # independent check: nowhere near the virtual 10 GB was ever produced
    assert fake.max_bytes_returned <= limit + avatars._UPLOAD_READ_CHUNK_SIZE


@pytest.mark.anyio
async def test_read_within_limit_accepts_upload_at_exactly_the_limit():
    fake = _HugeVirtualFile(chunk_size=avatars._UPLOAD_READ_CHUNK_SIZE, virtual_total=1024)

    # pyrefly: ignore [bad-argument-type]  # duck-typed stand-in, not a real UploadFile
    content = await avatars._read_within_limit(fake, limit=1024)

    assert len(content) == 1024


@pytest.mark.anyio
async def test_read_within_limit_rejects_upload_one_byte_over():
    fake = _HugeVirtualFile(chunk_size=avatars._UPLOAD_READ_CHUNK_SIZE, virtual_total=1025)

    with pytest.raises(avatars.UploadTooLarge):
        # pyrefly: ignore [bad-argument-type]  # duck-typed stand-in, not a real UploadFile
        await avatars._read_within_limit(fake, limit=1024)
