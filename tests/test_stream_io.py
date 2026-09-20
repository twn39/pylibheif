"""Tests for streaming I/O (read_from_stream, write_to_stream, PyStreamReader with 64KB buffer)."""

import io
import pytest
import numpy as np
from PIL import Image

import pylibheif
from pylibheif import (
    AsyncHeifContext,
    HeifChannel,
    HeifChroma,
    HeifColorspace,
    HeifCompressionFormat,
    HeifContext,
    HeifEncoder,
    HeifImage,
)


def make_test_image(width: int = 128, height: int = 96) -> HeifImage:
    """Create a gradient test HeifImage."""
    img = HeifImage(width, height, HeifColorspace.RGB, HeifChroma.InterleavedRGB)
    img.add_plane(HeifChannel.Interleaved, width, height, 8)
    plane = img.get_plane(HeifChannel.Interleaved, writeable=True)
    arr = np.asarray(plane)
    for y in range(height):
        for x in range(width):
            arr[y, x] = [x % 256, y % 256, (x + y) % 256]
    return img


def test_write_to_stream_and_read_from_stream():
    """Test full round-trip using io.BytesIO stream."""
    img = make_test_image(80, 60)
    ctx_write = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    enc.set_lossy_quality(85)
    enc.encode_image(ctx_write, img)

    bio = io.BytesIO()
    ctx_write.write_to_stream(bio)

    assert bio.tell() > 0
    raw_data = bio.getvalue()
    assert len(raw_data) > 0

    # Reset position and read from stream
    bio.seek(0)
    ctx_read = HeifContext()
    ctx_read.read_from_stream(bio)

    handle = ctx_read.get_primary_image_handle()
    assert handle.width == 80
    assert handle.height == 60

    decoded = handle.decode()
    assert decoded.width == 80
    assert decoded.height == 60


def test_stream_reader_large_file_buffering():
    """Test reading larger file to verify 64KB read-ahead buffering boundary transitions."""
    # 400x300 image produces a compressed file > 30KB
    img = make_test_image(400, 300)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    enc.set_lossless(True)
    enc.encode_image(ctx, img)

    bio = io.BytesIO()
    ctx.write_to_stream(bio)
    bio.seek(0)

    # Wrap in custom tracking stream to count read calls
    class TrackingStream:
        def __init__(self, raw: io.BytesIO):
            self.raw = raw
            self.read_calls = 0

        def read(self, size: int = -1):
            self.read_calls += 1
            return self.raw.read(size)

        def seek(self, offset: int, whence: int = 0):
            return self.raw.seek(offset, whence)

        def tell(self):
            return self.raw.tell()

    tracking = TrackingStream(bio)
    ctx_stream = HeifContext()
    ctx_stream.read_from_stream(tracking)

    handle = ctx_stream.get_primary_image_handle()
    assert handle.width == 400
    assert handle.height == 300
    # Because of 64KB read-ahead buffer, read_calls should be very few despite thousands of box parses
    assert tracking.read_calls < 50


@pytest.mark.asyncio
async def test_async_stream_read_and_write():
    """Test AsyncHeifContext stream methods."""
    img = make_test_image(64, 64)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    enc.encode_image(ctx, img)

    stream_out = io.BytesIO()
    ctx.write_to_stream(stream_out)
    stream_out.seek(0)

    async_ctx = await AsyncHeifContext.from_stream(stream_out)
    handle = async_ctx.get_primary_image_handle()
    assert handle.width == 64
    assert handle.height == 64

    decoded = await handle.decode()
    assert decoded.width == 64

    # Test async write_to_stream with new context
    new_ctx = AsyncHeifContext()
    encoder = pylibheif.AsyncHeifEncoder(HeifCompressionFormat.HEVC)
    await encoder.encode_image(new_ctx, decoded)

    stream_async_out = io.BytesIO()
    await new_ctx.write_to_stream(stream_async_out)
    assert stream_async_out.tell() > 0


def test_pillow_stream_io_integration():
    """Verify Pillow Image.open and save with BytesIO automatically use streaming."""
    from pylibheif.pillow import register_heif_opener, unregister_heif_opener

    register_heif_opener()
    try:
        pil_im = Image.new("RGB", (72, 48), (255, 128, 64))
        bio = io.BytesIO()
        pil_im.save(bio, format="HEIF", lossless=True)
        assert bio.tell() > 0

        bio.seek(0)
        loaded = Image.open(bio)
        assert loaded.size == (72, 48)
        assert loaded.mode == "RGB"
        # Force load
        loaded.load()
        px = loaded.getpixel((0, 0))
        assert abs(px[0] - 255) <= 2
        assert abs(px[1] - 128) <= 2
        assert abs(px[2] - 64) <= 2
    finally:
        unregister_heif_opener()


def test_writer_buffering_reduces_write_calls():
    """Verify PyStreamWriter buffers output into batches, significantly reducing write calls."""
    img = make_test_image(300, 200)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    enc.set_lossless(True)
    enc.encode_image(ctx, img)

    class TrackingWriteStream:
        def __init__(self):
            self.buffer = bytearray()
            self.write_calls = 0

        def write(self, data: bytes):
            self.write_calls += 1
            self.buffer.extend(data)
            return len(data)

    tracking = TrackingWriteStream()
    ctx.write_to_stream(tracking)

    assert len(tracking.buffer) > 10000
    # Before buffering, libheif invoked write hundreds of times.
    # With 64KB buffering, a ~18KB payload takes only 1 write (flush at end).
    assert tracking.write_calls <= 5, (
        f"Expected <= 5 write calls, got {tracking.write_calls}"
    )

    # Verify data written is valid by reading it back
    bio = io.BytesIO(bytes(tracking.buffer))
    ctx_read = HeifContext()
    ctx_read.read_from_stream(bio)
    handle = ctx_read.get_primary_image_handle()
    assert handle.width == 300
    assert handle.height == 200


def test_writer_exception_preservation():
    """Verify exceptions thrown by Python stream.write are preserved with original type and message."""
    img = make_test_image(64, 64)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    enc.encode_image(ctx, img)

    class FailingWriteStream:
        def write(self, data: bytes):
            raise PermissionError("Custom disk write access denied")

    failing_stream = FailingWriteStream()
    with pytest.raises(PermissionError, match="Custom disk write access denied"):
        ctx.write_to_stream(failing_stream)


def test_reader_without_readinto_fallback():
    """Verify PyStreamReader gracefully falls back to read() when stream lacks readinto()."""
    img = make_test_image(80, 60)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    enc.encode_image(ctx, img)

    bio = io.BytesIO()
    ctx.write_to_stream(bio)
    raw = bio.getvalue()

    class StreamWithoutReadinto:
        def __init__(self, data: bytes):
            self.data = data
            self.pos = 0

        def read(self, size: int = -1):
            if size < 0 or self.pos + size > len(self.data):
                chunk = self.data[self.pos :]
                self.pos = len(self.data)
            else:
                chunk = self.data[self.pos : self.pos + size]
                self.pos += size
            return chunk

        def seek(self, offset: int, whence: int = 0):
            if whence == 0:
                self.pos = offset
            elif whence == 1:
                self.pos += offset
            elif whence == 2:
                self.pos = len(self.data) + offset
            return self.pos

        def tell(self):
            return self.pos

    stream = StreamWithoutReadinto(raw)
    ctx_read = HeifContext()
    ctx_read.read_from_stream(stream)
    handle = ctx_read.get_primary_image_handle()
    assert handle.width == 80
    assert handle.height == 60
    decoded = handle.decode()
    assert decoded.width == 80


def test_reader_short_read_packing():
    """Verify PyStreamReader short-read loop packs small socket/pipe chunks into full buffers."""
    img = make_test_image(120, 90)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    enc.set_lossless(True)
    enc.encode_image(ctx, img)

    bio = io.BytesIO()
    ctx.write_to_stream(bio)
    raw = bio.getvalue()

    class ShortReadStream:
        def __init__(self, data: bytes, chunk_limit: int = 512):
            self.data = data
            self.pos = 0
            self.chunk_limit = chunk_limit

        def readinto(self, buffer):
            if self.pos >= len(self.data):
                return 0
            to_read = min(len(buffer), self.chunk_limit, len(self.data) - self.pos)
            buffer[:to_read] = self.data[self.pos : self.pos + to_read]
            self.pos += to_read
            return to_read

        def read(self, size: int = -1):
            if size < 0 or self.pos + size > len(self.data):
                chunk = self.data[self.pos :]
                self.pos = len(self.data)
            else:
                chunk = self.data[self.pos : self.pos + size]
                self.pos += size
            return chunk

        def seek(self, offset: int, whence: int = 0):
            if whence == 0:
                self.pos = offset
            elif whence == 1:
                self.pos += offset
            elif whence == 2:
                self.pos = len(self.data) + offset
            return self.pos

        def tell(self):
            return self.pos

    stream = ShortReadStream(raw, chunk_limit=512)
    ctx_read = HeifContext()
    ctx_read.read_from_stream(stream)
    handle = ctx_read.get_primary_image_handle()
    assert handle.width == 120
    assert handle.height == 90
    decoded = handle.decode()
    assert decoded.width == 120
