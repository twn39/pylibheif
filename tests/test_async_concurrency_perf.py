import asyncio
import concurrent.futures
import pathlib
import pytest
import numpy as np

import pylibheif
from pylibheif import (
    AsyncHeifContext,
    AsyncHeifEncoder,
    HeifImage,
    HeifColorspace,
    HeifChroma,
    HeifCompressionFormat,
)

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
SAMPLE_HEIC = PROJECT_ROOT / "images" / "test.heic"


@pytest.mark.asyncio
async def test_async_factory_from_file():
    """Test AsyncHeifContext.from_file classmethod."""
    async with await AsyncHeifContext.from_file(str(SAMPLE_HEIC)) as ctx:
        handle = ctx.get_primary_image_handle()
        assert handle.width > 0
        assert handle.height > 0
        img = await handle.decode()
        assert img.width == handle.width
        assert img.height == handle.height


@pytest.mark.asyncio
async def test_async_factory_from_memory():
    """Test AsyncHeifContext.from_memory classmethod."""
    data = SAMPLE_HEIC.read_bytes()
    async with await AsyncHeifContext.from_memory(data) as ctx:
        handle = ctx.get_primary_image_handle()
        assert handle.width > 0
        assert handle.height > 0


@pytest.mark.asyncio
async def test_custom_executor_injection():
    """Test custom ThreadPoolExecutor injection in AsyncHeifContext & AsyncHeifEncoder."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        async with await AsyncHeifContext.from_file(
            str(SAMPLE_HEIC), executor=executor
        ) as ctx:
            handle = ctx.get_primary_image_handle()
            assert handle._executor is executor

            img = await handle.decode()
            assert img.width > 0

            encoder = AsyncHeifEncoder(HeifCompressionFormat.HEVC, executor=executor)
            out_ctx = AsyncHeifContext(executor=executor)
            encoded_handle = await encoder.encode_image(out_ctx, img)
            assert encoded_handle.width == img.width

            data = await out_ctx.write_to_bytes()
            assert len(data) > 0


@pytest.mark.asyncio
async def test_async_metadata_methods():
    """Test async metadata methods on AsyncHeifContext & AsyncHeifImageHandle."""
    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    img = HeifImage.from_numpy(arr)

    encoder = AsyncHeifEncoder(HeifCompressionFormat.HEVC)
    out_ctx = AsyncHeifContext()
    handle = await encoder.encode_image(out_ctx, img)

    exif_data = b"EXIF\x00\x00test_exif_data"
    await out_ctx.add_exif_metadata_async(handle, exif_data)

    encoded_bytes = await out_ctx.write_to_bytes()
    assert len(encoded_bytes) > 0

    read_ctx = await AsyncHeifContext.from_memory(encoded_bytes)
    read_handle = read_ctx.get_primary_image_handle()

    raw_profile = await read_handle.get_raw_color_profile_async()
    assert isinstance(raw_profile, bytes)


@pytest.mark.asyncio
async def test_concurrent_async_decoding_throughput():
    """Test concurrent decoding under asyncio.gather using GIL-released background workers."""
    data = SAMPLE_HEIC.read_bytes()
    num_concurrent = 8

    async def decode_task(index: int):
        async with await AsyncHeifContext.from_memory(data) as ctx:
            handle = ctx.get_primary_image_handle()
            img = await handle.decode(HeifColorspace.RGB, HeifChroma.InterleavedRGB)
            plane = img.get_plane(pylibheif.HeifChannel.Interleaved)
            return plane.shape

    results = await asyncio.gather(*[decode_task(i) for i in range(num_concurrent)])
    assert len(results) == num_concurrent
    for shape in results:
        assert len(shape) == 3
        assert shape[2] == 3
