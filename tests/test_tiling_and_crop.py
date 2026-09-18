"""Tests for in-place crop and tiling/grid APIs."""

import numpy as np

from pylibheif import (
    HeifChannel,
    HeifChroma,
    HeifColorspace,
    HeifCompressionFormat,
    HeifContext,
    HeifEncoder,
    HeifImage,
    HeifImageTiling,
)


def make_test_image(width: int = 100, height: int = 80) -> HeifImage:
    img = HeifImage(width, height, HeifColorspace.RGB, HeifChroma.InterleavedRGB)
    img.add_plane(HeifChannel.Interleaved, width, height, 8)
    plane = img.get_plane(HeifChannel.Interleaved, writeable=True)
    arr = np.asarray(plane)
    for y in range(height):
        for x in range(width):
            arr[y, x] = [x % 256, y % 256, 128]
    return img


def test_heif_image_crop_in_place():
    """Test cropping a decoded HeifImage in place."""
    img = make_test_image(100, 80)
    assert img.width == 100
    assert img.height == 80

    # Crop 10 pixels from left, 10 from right, 5 from top, 5 from bottom
    img.crop(10, 10, 5, 5)

    assert img.width == 80
    assert img.height == 70

    plane = img.get_plane(HeifChannel.Interleaved)
    arr = np.asarray(plane)
    assert arr.shape == (70, 80, 3)
    # The new top-left pixel (0, 0) should correspond to old (10, 5)
    assert arr[0, 0, 0] == 10
    assert arr[0, 0, 1] == 5
    assert arr[0, 0, 2] == 128


def test_image_handle_tiling():
    """Test querying image tiling on standard image."""
    img = make_test_image(64, 64)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    enc.encode_image(ctx, img)

    handle = ctx.get_primary_image_handle()
    tiling = handle.get_image_tiling()
    assert isinstance(tiling, HeifImageTiling)
    assert tiling.image_width == 64
    assert tiling.image_height == 64
    assert tiling.num_columns >= 1
    assert tiling.num_rows >= 1
