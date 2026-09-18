"""Unit tests for pylibheif Pillow integration and plugin."""

import io
import os
import pytest
import numpy as np
from PIL import Image, ImageOps

import pylibheif
from pylibheif.pillow import (
    DISPLAY_P3_ICC_BYTES,
    from_pillow,
    register_heif_opener,
    to_pillow,
    unregister_heif_opener,
)


@pytest.fixture(autouse=True)
def cleanup_pillow_opener():
    """Ensure opener is cleanly registered/unregistered around tests."""
    yield
    unregister_heif_opener()


def test_from_pillow_and_to_pillow_rgb():
    """Test converting RGB PIL.Image to HeifImage and back."""
    orig = Image.new("RGB", (64, 48), (200, 100, 50))
    heif_img, info = from_pillow(orig)

    assert heif_img.width == 64
    assert heif_img.height == 48

    # Convert back
    back = to_pillow(heif_img)
    assert back.size == (64, 48)
    assert back.mode == "RGB"
    assert back.getpixel((10, 10)) == (200, 100, 50)


def test_from_pillow_and_to_pillow_rgba():
    """Test converting RGBA PIL.Image to HeifImage and back."""
    orig = Image.new("RGBA", (32, 32), (50, 150, 250, 128))
    heif_img, info = from_pillow(orig)

    assert heif_img.width == 32
    assert heif_img.height == 32

    # Convert back
    back = to_pillow(heif_img)
    assert back.size == (32, 32)
    assert back.mode == "RGBA"
    assert back.getpixel((0, 0)) == (50, 150, 250, 128)


def test_from_pillow_grayscale_l():
    """Test converting L mode grayscale PIL.Image to HeifImage."""
    orig = Image.new("L", (40, 40), 180)
    heif_img, info = from_pillow(orig)

    assert heif_img.width == 40
    assert heif_img.height == 40
    back = to_pillow(heif_img)
    # Converted back through RGB
    assert back.getpixel((5, 5)) == (180, 180, 180)


def test_convenience_methods_on_heif_types():
    """Test .to_pillow() on HeifImage / HeifImageHandle and HeifImage.from_pillow()."""
    pil_in = Image.new("RGB", (20, 20), (10, 20, 30))
    heif_img = pylibheif.HeifImage.from_pillow(pil_in)
    assert heif_img.width == 20

    pil_out = heif_img.to_pillow()
    assert pil_out.size == (20, 20)

    # Test handle.to_pillow() with existing test image
    test_heic = os.path.join(os.path.dirname(__file__), "..", "images", "test.heic")
    if os.path.exists(test_heic):
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(test_heic)
        handle = ctx.get_primary_image_handle()
        pil_from_handle = handle.to_pillow()
        assert pil_from_handle.size == (1440, 960)
        assert pil_from_handle.mode == "RGB"


def test_pillow_opener_registration_and_open():
    """Test register_pillow_opener with Image.open."""
    test_heic = os.path.join(os.path.dirname(__file__), "..", "images", "test.heic")
    if not os.path.exists(test_heic):
        pytest.skip("images/test.heic not found")

    register_heif_opener()

    im = Image.open(test_heic)
    assert im.format == "HEIF"
    assert im.size == (1440, 960)
    assert im.mode == "RGB"
    assert getattr(im, "n_frames", 1) == 1
    assert not getattr(im, "is_animated", False)

    # Ensure lazy decode works on pixel access
    px = im.getpixel((0, 0))
    assert isinstance(px, tuple)
    assert len(px) == 3


def test_pillow_save_and_open_roundtrip():
    """Test saving PIL Image as HEIF and opening back with Pillow."""
    register_heif_opener()

    orig = Image.new("RGB", (80, 60), (34, 139, 34))
    bio = io.BytesIO()

    orig.save(bio, format="HEIF", quality=85)
    assert bio.tell() > 0

    bio.seek(0)
    loaded = Image.open(bio)
    assert loaded.format == "HEIF"
    assert loaded.size == (80, 60)
    assert loaded.mode == "RGB"

    px = loaded.getpixel((10, 10))
    assert isinstance(px, tuple)
    # Lossy encoding tolerance
    assert abs(px[0] - 34) < 10
    assert abs(px[1] - 139) < 10
    assert abs(px[2] - 34) < 10


def test_exif_metadata_and_orientation_reset():
    """Test EXIF preservation and Orientation reset to 1 to avoid double-rotation."""
    register_heif_opener()

    orig = Image.new("RGB", (60, 40), (255, 255, 0))
    exif = orig.getexif()
    exif[0x0131] = "pylibheif-test-suite"
    exif[0x0112] = 6  # Orientation 6: 90 deg CW

    bio = io.BytesIO()
    orig.save(bio, format="HEIF", exif=exif)

    bio.seek(0)
    loaded = Image.open(bio)

    assert "exif" in loaded.info
    parsed_exif = loaded.getexif()
    assert parsed_exif.get(0x0131) == "pylibheif-test-suite"
    # Orientation must be reset to 1 so ImageOps.exif_transpose does not double-rotate
    assert parsed_exif.get(0x0112) == 1
    # Original orientation should be preserved in info
    assert loaded.info.get("original_orientation") == 6

    # Test exif_transpose: should be a no-op since orientation was reset
    transposed = ImageOps.exif_transpose(loaded)
    assert transposed.size == (60, 40)


def test_icc_profile_preservation():
    """Test ICC Profile preservation through Pillow save and open."""
    register_heif_opener()

    orig = Image.new("RGB", (50, 50), (10, 20, 30))
    orig.info["icc_profile"] = DISPLAY_P3_ICC_BYTES

    bio = io.BytesIO()
    orig.save(bio, format="HEIF")

    bio.seek(0)
    loaded = Image.open(bio)
    assert "icc_profile" in loaded.info
    assert loaded.info["icc_profile"] == DISPLAY_P3_ICC_BYTES


def test_nclx_display_p3_synthesis():
    """Test automatic Display P3 ICC profile synthesis when NCLX has primaries 12."""
    register_heif_opener()

    arr = np.zeros((30, 30, 3), dtype=np.uint8)
    img = pylibheif.HeifImage.from_numpy(arr)

    # Set NCLX with Display P3
    nclx = pylibheif.HeifColorProfileNclx(
        pylibheif.HeifColorPrimaries.SMPTE_EG_432_1,
        pylibheif.HeifTransferCharacteristics.IEC_61966_2_1,
        pylibheif.HeifMatrixCoefficients.RGB_GBR,
        True,
    )
    img.set_nclx_color_profile(nclx)

    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    encoder.encode_image(ctx, img)
    data = ctx.write_to_bytes()

    loaded = Image.open(io.BytesIO(data))
    assert "nclx_profile" in loaded.info
    assert loaded.info["nclx_profile"]["color_primaries"] == 12
    # Verify auto-synthesized Display P3 ICC profile is present
    assert "icc_profile" in loaded.info
    assert loaded.info["icc_profile"] == DISPLAY_P3_ICC_BYTES


def test_multi_frame_support():
    """Test Pillow ImageSequence multi-frame navigation with seek and tell."""
    register_heif_opener()

    # Create a 2-frame HEIF
    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

    img1 = pylibheif.HeifImage.from_numpy(np.full((32, 32, 3), 50, dtype=np.uint8))
    img2 = pylibheif.HeifImage.from_numpy(np.full((48, 48, 3), 150, dtype=np.uint8))

    encoder.encode_image(ctx, img1)
    encoder.encode_image(ctx, img2)

    data = ctx.write_to_bytes()

    im = Image.open(io.BytesIO(data))
    assert getattr(im, "n_frames", 1) == 2
    assert getattr(im, "is_animated", False)
    assert im.tell() == 0
    assert im.size == (32, 32)
    assert im.getpixel((0, 0)) == (50, 50, 50)

    # Seek to frame 1
    im.seek(1)
    assert im.tell() == 1
    assert im.size == (48, 48)
    assert im.getpixel((0, 0)) == (150, 150, 150)

    # Seek out of bounds
    with pytest.raises(EOFError):
        im.seek(2)
