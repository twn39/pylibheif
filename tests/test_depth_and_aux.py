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
    _ = handle.depth_map
    _ = handle.portrait_matte


def test_depth_map_palettes_and_helpers():
    """Verify built-in colormap palettes are exactly 768 bytes (256 RGB entries)."""
    from pylibheif.depth import (
        GRAYSCALE_PALETTE,
        INFERNO_PALETTE,
        TURBO_PALETTE,
        VIRIDIS_PALETTE,
        DepthRepresentationType,
    )

    assert len(TURBO_PALETTE) == 768
    assert len(INFERNO_PALETTE) == 768
    assert len(VIRIDIS_PALETTE) == 768
    assert len(GRAYSCALE_PALETTE) == 768

    assert DepthRepresentationType.UNIFORM_INVERSE_Z == 0
    assert DepthRepresentationType.UNIFORM_DISPARITY == 1
    assert DepthRepresentationType.UNIFORM_Z == 2


def test_depth_map_domain_entity_synthetic(tmp_path):
    """Test DepthMap domain entity with synthetic image handles."""
    import numpy as np
    from pylibheif.depth import DepthMap

    img = HeifImage(32, 32, HeifColorspace.RGB, HeifChroma.InterleavedRGB)
    img.add_plane(HeifChannel.Interleaved, 32, 32, 8)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    master_handle = enc.encode_image(ctx, img, preset="ultrafast")

    depth_img = HeifImage(16, 16, HeifColorspace.Monochrome, HeifChroma.Monochrome)
    depth_img.add_plane(HeifChannel.Y, 16, 16, 8)
    aux_handle = enc.encode_image(ctx, depth_img, preset="ultrafast")
    ctx.assign_auxiliary_image(master_handle, aux_handle, "urn:com:apple:photo:2018:aux:depth")

    out_file = tmp_path / "synthetic_depth.heic"
    ctx.write_to_file(str(out_file))

    read_ctx = HeifContext()
    read_ctx.read_from_file(str(out_file))
    primary = read_ctx.get_primary_image_handle()
    aux_ids = primary.get_auxiliary_image_ids()
    assert len(aux_ids) >= 1
    depth_aux = primary.get_auxiliary_image_handle(aux_ids[0])

    dm = DepthMap(master_handle=primary, aux_handle=depth_aux, item_id=aux_ids[0])
    assert dm.width == 16
    assert dm.height == 16
    assert dm.bit_depth == 8
    assert "DepthMap" in repr(dm)
    assert dm.master_handle is primary
    assert dm.aux_handle is depth_aux

    # Decode raw & normalized
    raw = dm.decode(normalize=False)
    assert raw.shape == (16, 16)
    assert raw.dtype == np.uint8

    norm = dm.decode(normalize=True)
    assert norm.shape == (16, 16)
    assert norm.dtype == np.float32
    assert norm.max() <= 1.0

    # Pillow rendering
    pil_turbo = dm.to_pillow(colormap="turbo")
    assert pil_turbo.size == (16, 16)
    assert pil_turbo.mode == "RGB"

    pil_inferno = dm.to_pillow(colormap="inferno")
    assert pil_inferno.size == (16, 16)
    assert pil_inferno.mode == "RGB"

    pil_gray = dm.to_pillow(colormap="grayscale")
    assert pil_gray.size == (16, 16)
    assert pil_gray.mode == "L"

    # Metric depth when no info is present returns None
    assert dm.to_metric_depth() is None
    d_dict = dm.to_dict()
    assert d_dict["width"] == 16
    assert d_dict["height"] == 16


@pytest.mark.asyncio
async def test_async_depth_map_entity(tmp_path):
    """Test AsyncDepthMap async methods and delegation."""
    import numpy as np
    from pylibheif._async import AsyncHeifContext
    from pylibheif.depth import AsyncDepthMap, DepthMap

    img = HeifImage(32, 32, HeifColorspace.RGB, HeifChroma.InterleavedRGB)
    img.add_plane(HeifChannel.Interleaved, 32, 32, 8)
    ctx = HeifContext()
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    master_handle = enc.encode_image(ctx, img, preset="ultrafast")

    depth_img = HeifImage(16, 16, HeifColorspace.Monochrome, HeifChroma.Monochrome)
    depth_img.add_plane(HeifChannel.Y, 16, 16, 8)
    aux_handle = enc.encode_image(ctx, depth_img, preset="ultrafast")
    ctx.assign_auxiliary_image(master_handle, aux_handle, "urn:com:apple:photo:2018:aux:depth")

    out_file = tmp_path / "async_synthetic_depth.heic"
    ctx.write_to_file(str(out_file))

    actx = AsyncHeifContext()
    await actx.read_from_file(str(out_file))
    aprimary = actx.get_primary_image_handle()
    sync_handle = aprimary._handle
    aux_ids = sync_handle.get_auxiliary_image_ids()
    sync_aux = sync_handle.get_auxiliary_image_handle(aux_ids[0])

    sync_dm = DepthMap(master_handle=sync_handle, aux_handle=sync_aux, item_id=aux_ids[0])
    adm = AsyncDepthMap(master_handle=aprimary, sync_depth_map=sync_dm)

    assert adm.width == 16
    assert adm.height == 16
    assert "AsyncDepthMap" in repr(adm)

    decoded = await adm.decode_async(normalize=True)
    assert decoded.shape == (16, 16)
    assert decoded.dtype == np.float32

    pil_res = await adm.to_pillow_async(colormap="turbo")
    assert pil_res.size == (16, 16)

