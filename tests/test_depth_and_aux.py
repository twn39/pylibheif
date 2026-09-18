"""Tests for Depth Image, Auxiliary Images, and Gain Map semantic properties."""

import os
import pytest

from pylibheif import (
    HeifChannel,
    HeifChroma,
    HeifColorspace,
    HeifCompressionFormat,
    HeifContext,
    HeifEncoder,
    HeifImage,
)


def test_depth_properties_on_standard_image():
    """Verify depth properties on standard non-depth image return correct negative flags."""
    img = HeifImage(32, 32, HeifColorspace.RGB, HeifChroma.InterleavedRGB)
    img.add_plane(HeifChannel.Interleaved, 32, 32, 8)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    enc.encode_image(ctx, img)

    handle = ctx.get_primary_image_handle()
    assert handle.has_depth_image is False
    assert handle.get_number_of_depth_images() == 0
    assert handle.get_depth_image_ids() == []
    assert handle.has_gain_map is False
    assert handle.gain_map_ids == []

    with pytest.raises(RuntimeError):
        handle.get_primary_depth_image_handle()

    with pytest.raises(ValueError):
        handle.get_gain_map_handle()

    info = handle.get_depth_representation_info()
    assert info is None


def test_existing_sample_image_depth_and_aux():
    """Test sample image if present."""
    sample_path = os.path.join(os.path.dirname(__file__), "..", "images", "test.heic")
    if not os.path.exists(sample_path):
        pytest.skip("images/test.heic not available")

    ctx = HeifContext()
    ctx.read_from_file(sample_path)
    handle = ctx.get_primary_image_handle()

    # Query without crashing
    _ = handle.has_depth_image
    _ = handle.has_gain_map
    _ = handle.get_auxiliary_image_ids()
