"""Tests for primary image designation, container brands customization, and lock-free preset concurrency."""

import concurrent.futures
import pytest
import numpy as np

import pylibheif
from pylibheif import (
    HeifContext,
    AsyncHeifContext,
    HeifImage,
    HeifEncoder,
    HeifCompressionFormat,
)


def make_test_image(width: int, height: int, color_val: int) -> HeifImage:
    arr = np.full((height, width, 3), color_val, dtype=np.uint8)
    return HeifImage.from_numpy(arr)


def test_set_primary_image():
    """Test designating an arbitrary image handle as primary image."""
    ctx = HeifContext()
    encoder = HeifEncoder(HeifCompressionFormat.HEVC, preset="ultrafast")

    img1 = make_test_image(80, 60, 50)
    img2 = make_test_image(40, 30, 200)

    _ = encoder.encode_image(ctx, img1)
    h2 = encoder.encode_image(ctx, img2)

    # Initial primary is the first image added (80x60)
    primary = ctx.get_primary_image_handle()
    assert primary.width == 80
    assert primary.height == 60

    # Switch primary to h2 (40x30)
    ctx.set_primary_image(h2)

    primary_after = ctx.get_primary_image_handle()
    assert primary_after.width == 40
    assert primary_after.height == 30

    # Write out and read back to verify persistence in container
    data = ctx.write_to_bytes()
    assert len(data) > 0

    ctx_read = HeifContext()
    ctx_read.read_from_memory(data)

    primary_read = ctx_read.get_primary_image_handle()
    assert primary_read.width == 40
    assert primary_read.height == 30


@pytest.mark.asyncio
async def test_async_set_primary_image():
    """Test async context set_primary_image and set_primary_image_async."""
    ctx = HeifContext()
    encoder = HeifEncoder(HeifCompressionFormat.HEVC, preset="ultrafast")

    img1 = make_test_image(64, 64, 100)
    img2 = make_test_image(32, 32, 220)

    _ = encoder.encode_image(ctx, img1)
    h2 = encoder.encode_image(ctx, img2)

    async_ctx = AsyncHeifContext(ctx)
    await async_ctx.set_primary_image_async(h2)

    primary = async_ctx.get_primary_image_handle()
    assert primary.width == 32
    assert primary.height == 32


def test_set_major_and_compatible_brands():
    """Test custom major and compatible brands injection into ISOBMFF header."""
    ctx = HeifContext()
    encoder = HeifEncoder(HeifCompressionFormat.HEVC, preset="ultrafast")

    img = make_test_image(32, 32, 128)
    encoder.encode_image(ctx, img)

    ctx.set_major_brand("mif1")
    ctx.add_compatible_brand("heic")
    ctx.add_compatible_brand("geo1")

    data = bytes(ctx.write_to_bytes())

    # ISOBMFF header:
    # 0..3: box size (4 bytes)
    # 4..7: 'ftyp'
    # 8..11: major brand ('mif1')
    assert data[4:8] == b"ftyp"
    assert data[8:12] == b"mif1"
    # Compatible brands list should contain 'heic' and 'geo1'
    ftyp_box_size = int.from_bytes(data[0:4], "big")
    ftyp_data = data[:ftyp_box_size]
    assert b"heic" in ftyp_data
    assert b"geo1" in ftyp_data


def test_invalid_brand_arguments():
    """Test error handling when passing invalid brand strings."""
    ctx = HeifContext()
    with pytest.raises((ValueError, Exception)):
        ctx.set_major_brand("toolong")

    with pytest.raises((ValueError, Exception)):
        ctx.add_compatible_brand("sh")


def test_lock_free_preset_concurrency():
    """Test heavy concurrent access to get_default_encoder_preset and set_default_encoder_preset."""
    initial_preset = pylibheif.get_default_encoder_preset()

    def worker(worker_id: int):
        presets = ["ultrafast", "fast", "balanced", "quality"]
        for i in range(100):
            # Read preset
            p = pylibheif.get_default_encoder_preset()
            assert p in presets or p == initial_preset

            # Cycle preset setting
            if worker_id == 0 and i % 10 == 0:
                pylibheif.set_default_encoder_preset(presets[i % len(presets)])

            # Create encoder with preset
            enc = HeifEncoder(HeifCompressionFormat.HEVC, preset=p)
            assert enc.name != ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(worker, i) for i in range(16)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    # Reset back to initial
    pylibheif.set_default_encoder_preset(initial_preset)
