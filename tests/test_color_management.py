"""Unit tests for LittleCMS 2 precise color management in pylibheif."""

import io
import pytest
import numpy as np
from PIL import Image, ImageCms

import pylibheif
from pylibheif.color import (
    ADOBE_RGB_ICC_BYTES,
    DISPLAY_P3_ICC_BYTES,
    REC2020_ICC_BYTES,
    SRGB_ICC_BYTES,
    RenderingIntent,
    _get_cached_transform,
    _numpy_color_transform_fallback,
    get_profile_info,
    nclx_to_icc_profile,
    transform_colorspace,
)
from pylibheif.pillow import register_pillow_opener, to_pillow


def test_embedded_profiles_integrity():
    """Verify that all embedded profiles parse cleanly in LittleCMS without errors."""
    for name, p_bytes in [
        ("Display P3", DISPLAY_P3_ICC_BYTES),
        ("Adobe RGB", ADOBE_RGB_ICC_BYTES),
        ("Rec.2020", REC2020_ICC_BYTES),
        ("sRGB", SRGB_ICC_BYTES),
    ]:
        assert len(p_bytes) > 500
        p_obj = ImageCms.ImageCmsProfile(io.BytesIO(p_bytes))
        desc = ImageCms.getProfileDescription(p_obj)
        assert len(desc.strip()) > 0


def test_get_profile_info_and_wide_gamut():
    """Test get_profile_info metadata extraction and wide-gamut detection."""
    p3_info = get_profile_info(DISPLAY_P3_ICC_BYTES)
    assert p3_info["is_wide_gamut"] is True
    assert p3_info["color_space"] == "RGB"
    assert "P3" in p3_info["name"] or "Display" in p3_info["name"]

    adobe_info = get_profile_info(ADOBE_RGB_ICC_BYTES)
    assert adobe_info["is_wide_gamut"] is True
    assert "Adobe" in adobe_info["name"]

    rec2020_info = get_profile_info(REC2020_ICC_BYTES)
    assert rec2020_info["is_wide_gamut"] is True
    assert "2020" in rec2020_info["name"]

    srgb_info = get_profile_info(SRGB_ICC_BYTES)
    assert srgb_info["is_wide_gamut"] is False
    assert "sRGB" in srgb_info["name"] or "srgb" in srgb_info["name"].lower()


def test_nclx_to_icc_profile_mapping():
    """Test mapping of NCLX color primaries to canonical ICC profiles."""
    class DummyNclx:
        def __init__(self, primaries):
            self.color_primaries = primaries

    # Primaries 12 -> Display P3
    assert nclx_to_icc_profile(DummyNclx(12)) == DISPLAY_P3_ICC_BYTES
    # Primaries 11 -> Display P3 / DCI P3
    assert nclx_to_icc_profile(DummyNclx(11)) == DISPLAY_P3_ICC_BYTES
    # Primaries 9 -> Rec.2020
    assert nclx_to_icc_profile(DummyNclx(9)) == REC2020_ICC_BYTES
    # Primaries 1 -> sRGB / BT.709
    assert nclx_to_icc_profile(DummyNclx(1)) == SRGB_ICC_BYTES
    # None -> sRGB
    assert nclx_to_icc_profile(None) == SRGB_ICC_BYTES


def test_transform_colorspace_display_p3_to_srgb():
    """Test transforming pixels from Display P3 to sRGB."""
    # Pure Display P3 Green (0, 255, 0) is outside sRGB gamut
    # When transformed to sRGB, green remains high, but red/blue shift into gamut
    img_arr = np.zeros((20, 20, 3), dtype=np.uint8)
    img_arr[:, :] = [0, 255, 0]

    out_srgb = transform_colorspace(
        img_arr,
        src_profile="Display P3",
        dst_profile="sRGB",
        intent=RenderingIntent.PERCEPTUAL,
    )
    assert out_srgb.shape == (20, 20, 3)
    assert out_srgb.dtype == np.uint8
    # In sRGB, P3 pure green has non-zero red or blue due to gamut compression
    assert out_srgb[0, 0, 1] > 240


def test_alpha_channel_preservation():
    """Test that Alpha channel is preserved bit-for-bit without LittleCMS corruption."""
    h, w = 16, 16
    rgba_arr = np.zeros((h, w, 4), dtype=np.uint8)
    rgba_arr[:, :, 0] = 200
    rgba_arr[:, :, 1] = 100
    rgba_arr[:, :, 2] = 50
    # Create variable alpha values across pixels
    for y in range(h):
        for x in range(w):
            rgba_arr[y, x, 3] = (y * 16 + x) % 256

    original_alpha = rgba_arr[:, :, 3].copy()

    # Transform RGBA Display P3 -> sRGB
    out_rgba = transform_colorspace(
        rgba_arr,
        src_profile="Display P3",
        dst_profile="sRGB",
        intent="perceptual",
    )

    assert out_rgba.shape == (h, w, 4)
    # Crucial assertion: Alpha channel must be 100% identical!
    np.testing.assert_array_equal(out_rgba[:, :, 3], original_alpha)


def test_transform_caching_lru():
    """Test that LRU transform caching functions properly."""
    _get_cached_transform.cache_clear()
    info_before = _get_cached_transform.cache_info()
    assert info_before.currsize == 0

    img = np.zeros((8, 8, 3), dtype=np.uint8)
    # First call -> cache miss
    transform_colorspace(img, src_profile="Display P3", dst_profile="sRGB")
    info_after1 = _get_cached_transform.cache_info()
    assert info_after1.currsize == 1
    assert info_after1.hits == 0

    # Second call with same profiles -> cache hit!
    transform_colorspace(img, src_profile="Display P3", dst_profile="sRGB")
    info_after2 = _get_cached_transform.cache_info()
    assert info_after2.hits == 1


def test_numpy_fallback_transform():
    """Test pure NumPy Bradford fallback transformation."""
    h, w = 10, 10
    img = np.full((h, w, 4), [255, 128, 0, 180], dtype=np.uint8)
    out = _numpy_color_transform_fallback(
        img,
        src_bytes=DISPLAY_P3_ICC_BYTES,
        dst_bytes=SRGB_ICC_BYTES,
        as_pillow=False,
    )
    assert out.shape == (h, w, 4)
    assert out.dtype == np.uint8
    assert out[0, 0, 3] == 180  # Alpha preserved


def test_handle_decode_and_decode_to_srgb():
    """Test HeifImageHandle.decode_to_srgb() and decode(target_colorspace='sRGB')."""
    # Create a test HEIF image with Display P3 NCLX
    orig_im = Image.new("RGB", (32, 32), (255, 0, 0))
    bio = io.BytesIO()
    register_pillow_opener()
    orig_im.save(bio, format="HEIF", quality=90)
    bio.seek(0)

    ctx = pylibheif.HeifContext()
    ctx.read_from_memory(bio.getvalue())
    handle = ctx.get_primary_image_handle()

    # 1. Inspect color profile info
    info = handle.get_color_profile_info()
    assert "color_space" in info

    # 2. decode_to_srgb
    srgb_arr = handle.decode_to_srgb(intent="perceptual")
    assert isinstance(srgb_arr, np.ndarray)
    assert srgb_arr.shape == (32, 32, 3)

    # 3. decode with target_colorspace
    heif_img = handle.decode(target_colorspace="sRGB")
    assert isinstance(heif_img, pylibheif.HeifImage)
    assert heif_img.width == 32
    assert heif_img.height == 32


def test_pillow_convert_colorspace():
    """Test HeifImageFile.convert_colorspace() and to_pillow(target_colorspace='sRGB')."""
    register_pillow_opener()
    orig_im = Image.new("RGBA", (24, 24), (200, 50, 50, 190))
    bio = io.BytesIO()
    orig_im.save(bio, format="HEIF", quality=95)
    bio.seek(0)

    # Open with Pillow
    pil_im = Image.open(bio)
    assert hasattr(pil_im, "convert_colorspace")
    converted = pil_im.convert_colorspace("sRGB")
    assert isinstance(converted, Image.Image)
    assert converted.size == (24, 24)
    assert converted.mode == "RGBA"
    # Check alpha preserved
    arr = np.array(converted)
    assert abs(int(arr[0, 0, 3]) - 190) <= 2

    # to_pillow with target_colorspace
    ctx = pylibheif.HeifContext()
    ctx.read_from_memory(bio.getvalue())
    handle = ctx.get_primary_image_handle()
    pil_srgb = to_pillow(handle, target_colorspace="sRGB")
    assert pil_srgb.size == (24, 24)


@pytest.mark.asyncio
async def test_async_handle_color_management():
    """Test AsyncHeifImageHandle color management async methods."""
    orig_im = Image.new("RGB", (16, 16), (0, 128, 255))
    bio = io.BytesIO()
    register_pillow_opener()
    orig_im.save(bio, format="HEIF", quality=85)

    async_ctx = await pylibheif.AsyncHeifContext.from_memory(bio.getvalue())
    async_handle = await async_ctx.get_primary_image_handle_async()

    # Test get_color_profile_info_async
    c_info = await async_handle.get_color_profile_info_async()
    assert "color_space" in c_info

    # Test decode_to_srgb
    srgb_res = await async_handle.decode_to_srgb()
    assert isinstance(srgb_res, np.ndarray)

    # Test async decode with target_colorspace
    decoded_img = await async_handle.decode(target_colorspace="sRGB")
    assert isinstance(decoded_img, pylibheif.HeifImage)
    assert decoded_img.width == 16


def test_cli_convert_to_srgb(tmp_path):
    """Test CLI conversion with --to-srgb and --intent options."""
    from typer.testing import CliRunner
    from pylibheif.cli import app

    runner = CliRunner()
    src_path = tmp_path / "src.heic"
    dst_path = tmp_path / "out.jpg"

    # Create source HEIC
    register_pillow_opener()
    Image.new("RGB", (30, 30), (100, 200, 50)).save(str(src_path), format="HEIF")

    result = runner.invoke(
        app,
        [
            "convert",
            str(src_path),
            str(dst_path),
            "--to-srgb",
            "--intent",
            "perceptual",
            "--json",
            "-y",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert dst_path.exists()
    assert '"to_srgb": true' in result.stdout
