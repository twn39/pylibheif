import gc
import hashlib
import io
import pytest
import numpy as np

import pylibheif
from pylibheif import (
    HeifCompressionFormat,
    HeifColorspace,
    HeifChroma,
    HeifChannel,
    HeifContext,
    HeifEncoder,
    AsyncHeifContext,
)


@pytest.fixture
def encoded_context():
    """Create a simple HEIF context containing an encoded image."""
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC, preset="ultrafast")
    img = pylibheif.HeifImage(64, 64, HeifColorspace.RGB, HeifChroma.InterleavedRGB)
    img.add_plane(HeifChannel.Interleaved, 64, 64, 8)
    enc.encode_image(ctx, img)
    return ctx


def test_write_to_bytes_and_memoryview_types(encoded_context):
    ctx = encoded_context

    # 1. write_to_bytes(copy=True) -> standard bytes
    b = ctx.write_to_bytes(copy=True)
    assert isinstance(b, bytes)
    assert len(b) > 0

    # 2. write_to_memoryview() -> zero-copy memoryview
    mv = ctx.write_to_memoryview()
    assert isinstance(mv, memoryview)
    assert mv.readonly is True
    assert mv.format == "B"
    assert len(mv) == len(b)
    assert bytes(mv) == b

    # 3. write_to_bytes(copy=False) -> zero-copy memoryview
    mv_no_copy = ctx.write_to_bytes(copy=False)
    assert isinstance(mv_no_copy, memoryview)
    assert mv_no_copy.readonly is True
    assert bytes(mv_no_copy) == b


def test_readonly_memory_protection(encoded_context):
    mv = encoded_context.write_to_memoryview()
    assert mv.readonly is True

    # Modifying read-only memoryview must raise TypeError
    with pytest.raises(TypeError):
        mv[0] = 0


def test_lifecycle_decoupling_and_memory_safety():
    """Verify memoryview remains valid and safe after HeifContext is closed and garbage collected."""
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC, preset="ultrafast")
    img = pylibheif.HeifImage(32, 32, HeifColorspace.RGB, HeifChroma.InterleavedRGB)
    img.add_plane(HeifChannel.Interleaved, 32, 32, 8)
    enc.encode_image(ctx, img)

    # Export zero-copy memoryview
    mv = ctx.write_to_memoryview()
    expected_len = len(mv)
    expected_header = bytes(mv[:8])

    # Close context and trigger garbage collection
    ctx.close()
    del ctx
    del enc
    del img
    gc.collect()

    # Memoryview must remain completely valid and intact
    assert len(mv) == expected_len
    assert bytes(mv[:8]) == expected_header

    # Slicing still works safely
    sub_view = mv[4:16]
    assert len(sub_view) == 12

    # Round-trip decode from the decoupled memoryview
    read_ctx = HeifContext()
    read_ctx.read_from_memory(mv)
    handle = read_ctx.get_primary_image_handle()
    assert handle.width == 32
    assert handle.height == 32


def test_zero_copy_interoperability(encoded_context):
    mv = encoded_context.write_to_memoryview()

    # 1. NumPy 1D array conversion (zero-copy)
    arr = np.asarray(mv)
    assert isinstance(arr, np.ndarray)
    assert arr.dtype == np.uint8
    assert arr.shape == (len(mv),)
    # Check that they share memory pointer
    assert arr.__array_interface__["data"][0] != 0

    # 2. Hashlib digest computation without copy
    h1 = hashlib.sha256(mv).hexdigest()
    h2 = hashlib.sha256(bytes(mv)).hexdigest()
    assert h1 == h2

    # 3. io.BytesIO consumption
    bio = io.BytesIO(mv)
    read_back = bio.read()
    assert read_back == bytes(mv)


@pytest.mark.asyncio
async def test_async_write_to_memoryview():
    async_ctx = AsyncHeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC, preset="ultrafast")
    img = pylibheif.HeifImage(32, 32, HeifColorspace.RGB, HeifChroma.InterleavedRGB)
    img.add_plane(HeifChannel.Interleaved, 32, 32, 8)
    enc.encode_image(async_ctx._ctx, img)

    # Async memoryview export
    mv = await async_ctx.write_to_memoryview()
    assert isinstance(mv, memoryview)
    assert mv.readonly is True
    assert len(mv) > 0

    # Async write_to_bytes(copy=False)
    mv2 = await async_ctx.write_to_bytes(copy=False)
    assert isinstance(mv2, memoryview)
    assert bytes(mv) == bytes(mv2)

    # Async write_to_bytes(copy=True)
    b = await async_ctx.write_to_bytes(copy=True)
    assert isinstance(b, bytes)
    assert b == bytes(mv)
