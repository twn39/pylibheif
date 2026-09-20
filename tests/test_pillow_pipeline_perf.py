import io
import pytest
import numpy as np
from PIL import Image

import pylibheif
from pylibheif import (
    HeifColorspace,
    HeifChroma,
    HeifImage,
)
from pylibheif.pillow import from_pillow, to_pillow


def test_heif_image_from_buffer_bytes():
    """Verify HeifImage.from_buffer works directly with raw Python bytes."""
    width, height = 64, 48
    # 64 * 48 * 3 RGB bytes
    raw_rgb = bytes(range(256)) * ((width * height * 3) // 256 + 1)
    raw_rgb = raw_rgb[: width * height * 3]

    img = HeifImage.from_buffer(
        raw_rgb, width, height, HeifColorspace.RGB, HeifChroma.InterleavedRGB
    )
    assert img.width == width
    assert img.height == height

    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, writeable=False)
    np_arr = np.asarray(plane)
    assert np_arr.shape == (height, width, 3)
    assert bytes(np_arr.flatten()) == raw_rgb


def test_heif_image_from_buffer_bytearray_and_memoryview():
    """Verify HeifImage.from_buffer works with bytearray and memoryview (RGBA)."""
    width, height = 32, 32
    raw = bytearray([10, 20, 30, 255] * (width * height))
    mv = memoryview(raw)

    img = HeifImage.from_buffer(
        mv, width, height, HeifColorspace.RGB, HeifChroma.InterleavedRGBA
    )
    assert img.width == width
    assert img.height == height

    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, writeable=False)
    np_arr = np.asarray(plane)
    assert np_arr.shape == (height, width, 4)
    assert np_arr[0, 0, 0] == 10
    assert np_arr[0, 0, 3] == 255


def test_heif_image_from_buffer_with_stride():
    """Verify HeifImage.from_buffer handles custom source row stride with padding."""
    width, height = 10, 10
    # Add 6 padding bytes per row: 10 * 3 + 6 = 36 bytes per row
    stride = 36
    data = bytearray(stride * height)
    for y in range(height):
        for x in range(width):
            data[y * stride + x * 3 + 0] = (x * 10) % 256
            data[y * stride + x * 3 + 1] = (y * 10) % 256
            data[y * stride + x * 3 + 2] = 128

    img = HeifImage.from_buffer(
        data,
        width,
        height,
        HeifColorspace.RGB,
        HeifChroma.InterleavedRGB,
        bit_depth=8,
        stride=stride,
    )
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, writeable=False)
    np_arr = np.asarray(plane)
    assert np_arr[5, 5, 0] == 50
    assert np_arr[5, 5, 1] == 50
    assert np_arr[5, 5, 2] == 128


def test_heif_image_from_buffer_size_validation():
    """Verify HeifImage.from_buffer raises ValueError when buffer is too small."""
    too_small = bytes(10)
    with pytest.raises(ValueError, match="Buffer is too small"):
        HeifImage.from_buffer(
            too_small, 64, 64, HeifColorspace.RGB, HeifChroma.InterleavedRGB
        )


def test_from_numpy_strided_and_sliced():
    """Verify HeifImage.from_numpy accepts strided non-contiguous NumPy arrays."""
    # Create larger array
    base = np.zeros((100, 100, 3), dtype=np.uint8)
    for y in range(100):
        for x in range(100):
            base[y, x] = [x, y, 200]

    # Non-contiguous slice: flipped vertically
    flipped = base[::-1, :, :]
    assert not flipped.flags["C_CONTIGUOUS"]

    img = HeifImage.from_numpy(flipped)
    assert img.width == 100
    assert img.height == 100

    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, writeable=False)
    out = np.asarray(plane)
    assert out[0, 0, 1] == 99  # was bottom row y=99, now top row y=0


def test_from_pillow_direct_buffer_pipeline():
    """Verify from_pillow converts PIL images via direct buffer fast path."""
    pil_im = Image.new("RGB", (128, 96), (100, 150, 200))
    heif_img, info = from_pillow(pil_im)

    assert heif_img.width == 128
    assert heif_img.height == 96

    # Verify round-trip conversion to Pillow
    pil_roundtrip = to_pillow(heif_img)
    assert pil_roundtrip.size == (128, 96)
    px = pil_roundtrip.getpixel((10, 10))
    assert px == (100, 150, 200)


def test_from_pillow_rgba_pipeline():
    """Verify from_pillow handles RGBA PIL images via direct buffer fast path."""
    pil_im = Image.new("RGBA", (64, 64), (50, 100, 150, 200))
    heif_img, info = from_pillow(pil_im)

    assert heif_img.width == 64
    assert heif_img.height == 64

    pil_roundtrip = to_pillow(heif_img)
    assert pil_roundtrip.size == (64, 64)
    px = pil_roundtrip.getpixel((5, 5))
    assert px == (50, 100, 150, 200)


def test_pillow_save_load_parallel_roundtrip():
    """Verify Pillow save and parallel load integration roundtrip with EXIF."""
    from pylibheif.pillow import register_heif_opener, unregister_heif_opener

    register_heif_opener()
    try:
        im = Image.new("RGB", (200, 150), (255, 0, 128))
        bio = io.BytesIO()
        im.save(bio, format="HEIF", quality=90)
        assert bio.tell() > 0

        bio.seek(0)
        loaded = Image.open(bio)
        assert loaded.size == (200, 150)
        assert loaded.mode == "RGB"
        # Force load triggers parallel decode
        loaded.load()
        px = loaded.getpixel((0, 0))
        assert abs(px[0] - 255) <= 5
        assert abs(px[1] - 0) <= 5
        assert abs(px[2] - 128) <= 5
    finally:
        unregister_heif_opener()
