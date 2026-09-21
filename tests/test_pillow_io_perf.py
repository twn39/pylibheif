"""Tests for Pillow plugin I/O performance optimizations and robustness."""

import io
import os
import tempfile
from typing import Any, Tuple, cast
import numpy as np
import pytest
from PIL import Image

from pylibheif import (
    HeifImage,
    register_pillow_opener,
    unregister_pillow_opener,
)
from pylibheif.pillow import to_pillow


@pytest.fixture(autouse=True)
def setup_teardown_pillow():
    register_pillow_opener()
    yield
    unregister_pillow_opener()


def test_bytesio_read_and_save_direct_fast_path():
    """Verify Image.open and im.save with io.BytesIO use direct memory path correctly."""
    # 1. Create source image
    orig = Image.new("RGB", (128, 96), (180, 90, 45))
    bio = io.BytesIO()

    # 2. Save to BytesIO (triggers write_to_memoryview fast path)
    orig.save(bio, format="HEIF", quality=85)
    assert bio.tell() > 0

    # 3. Open from BytesIO (triggers getbuffer() read_from_memory fast path)
    bio.seek(0)
    loaded = Image.open(bio)
    assert loaded.format == "HEIF"
    assert loaded.size == (128, 96)
    assert loaded.mode == "RGB"

    # 4. Trigger pixel load
    loaded.load()
    px = cast(Tuple[int, int, int], loaded.getpixel((10, 10)))
    assert abs(px[0] - 180) <= 5
    assert abs(px[1] - 90) <= 5
    assert abs(px[2] - 45) <= 5
    loaded.close()


def test_closed_file_object_immunity():
    """Verify opening an open() file handle is immune to file closure before load()."""
    with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Create and save a valid HEIC file to disk
        orig = Image.new("RGB", (64, 64), (10, 200, 50))
        orig.save(tmp_path, format="HEIF", quality=80)

        # Open file object inside with-statement, then close it
        with open(tmp_path, "rb") as f:
            im = Image.open(f)
            assert im.size == (64, 64)

        # f is now closed!
        assert f.closed

        # Calling load() after f is closed should succeed because C++ context opened path directly
        im.load()
        px = cast(Tuple[int, int, int], im.getpixel((5, 5)))
        assert abs(px[0] - 10) <= 5
        assert abs(px[1] - 200) <= 5
        assert abs(px[2] - 50) <= 5
        im.close()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_multiframe_streaming_save():
    """Verify multi-frame animated save streams frames without memory retention."""
    frames = [
        Image.new("RGB", (64, 64), (255, 0, 0)),
        Image.new("RGB", (64, 64), (0, 255, 0)),
        Image.new("RGB", (64, 64), (0, 0, 255)),
    ]
    durations = [150, 250, 350]

    bio = io.BytesIO()
    frames[0].save(
        bio,
        format="AVIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        concurrency_budget="throughput",
    )
    assert bio.tell() > 0

    # Read back and verify frames
    bio.seek(0)
    loaded = Image.open(bio)
    assert getattr(loaded, "is_animated", False) is True
    assert getattr(loaded, "n_frames", 1) == 3

    # Check frame 0
    loaded.seek(0)
    loaded.load()
    px0 = cast(Tuple[int, int, int], loaded.getpixel((10, 10)))
    assert px0[0] > 200 and px0[1] < 30 and px0[2] < 30

    # Check frame 1
    loaded.seek(1)
    loaded.load()
    px1 = cast(Tuple[int, int, int], loaded.getpixel((10, 10)))
    assert px1[1] > 200 and px1[0] < 30 and px1[2] < 30

    # Check frame 2
    loaded.seek(2)
    loaded.load()
    px2 = cast(Tuple[int, int, int], loaded.getpixel((10, 10)))
    assert px2[2] > 200 and px2[0] < 30 and px2[1] < 30

    loaded.close()


def test_readonly_uint16_downsampling_safety():
    """Verify high bit-depth uint16 downsampling does not crash on read-only buffers."""
    width, height = 32, 32
    # 10-bit image values [0..1023]
    raw_10bit = np.full((height, width, 3), 800, dtype=np.uint16)
    img = HeifImage.from_numpy(raw_10bit, bit_depth=10)

    # Convert to pillow with convert_hdr_to_8bit=True
    pil_img = to_pillow(img, convert_hdr_to_8bit=True)
    assert pil_img.size == (width, height)
    assert pil_img.mode == "RGB"

    # 800 >> 2 = 200
    px = cast(Tuple[int, int, int], pil_img.getpixel((0, 0)))
    assert px == (200, 200, 200)


def test_rgba_zerocopy_frombuffer_integration():
    """Verify RGBA 8-bit images take advantage of zero-copy buffer loading."""
    orig = Image.new("RGBA", (48, 48), (120, 60, 240, 200))
    bio = io.BytesIO()
    orig.save(bio, format="HEIF", quality=90)

    bio.seek(0)
    loaded = Image.open(bio)
    assert loaded.mode == "RGBA"
    loaded.load()
    px = cast(Tuple[int, int, int, int], loaded.getpixel((5, 5)))
    assert abs(px[0] - 120) <= 10
    assert abs(px[1] - 60) <= 10
    assert abs(px[2] - 240) <= 10
    assert abs(px[3] - 200) <= 10
    loaded.close()


def test_deterministic_context_closure():
    """Verify that single-frame load releases context and close() cleans up deterministically."""
    orig = Image.new("RGB", (32, 32), (10, 20, 30))
    bio = io.BytesIO()
    orig.save(bio, format="HEIF")

    bio.seek(0)
    loaded = Image.open(bio)
    any_loaded = cast(Any, loaded)
    assert any_loaded._ctx is not None

    # Load should release _ctx for single-frame
    loaded.load()
    assert any_loaded._ctx is None
    assert any_loaded._handle is None

    # Explicit close() should safely run without errors
    loaded.close()
    assert any_loaded._ctx is None
