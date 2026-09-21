"""Comprehensive test suite for HDR / Ultra HDR / Gain Map pipeline.

Covers:
1. GainMapMetadata parsing, serialization, and ISO 21496-1 / Apple format support.
2. EOTF linearization, ST 2084 PQ encoding, and bilinear resampling.
3. reconstruct_hdr tonemapping accuracy across float32, float16, and PQ uint16 formats.
4. C++ assign_auxiliary_image binding, auxC box, and ISOBMFF auxiliary image reading.
5. Pillow plugin im.save(..., gain_map=...), im.get_gain_map(), and im.render_hdr().
6. CLI info and convert commands with --extract-gain-map and --render-hdr.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import pylibheif
from pylibheif.gain_map import (
    GainMapMetadata,
    linear_to_pq,
    linear_to_srgb,
    reconstruct_hdr,
    resample_gain_map,
    srgb_to_linear,
)

try:
    from PIL import Image
    from pylibheif.pillow import register_pillow_opener
    from pylibheif.pillow.plugin import HeifImageFile

    register_pillow_opener()
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


# =====================================================================
# 1. GainMapMetadata Tests
# =====================================================================


def test_gain_map_metadata_defaults() -> None:
    meta = GainMapMetadata()
    assert meta.gain_map_min == (0.0, 0.0, 0.0)
    assert meta.gain_map_max == (2.0, 2.0, 2.0)
    assert meta.gamma == (1.0, 1.0, 1.0)
    assert meta.hdr_capacity_min == 0.0
    assert meta.hdr_capacity_max == 2.0
    assert meta.format_type == "ISO"
    assert abs(meta.max_content_boost - 4.0) < 1e-5


def test_gain_map_metadata_apple_xmp_roundtrip() -> None:
    apple_xmp = (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description xmlns:HDRGainMap="http://ns.apple.com/HDRGainMap/1.0/" '
        b'HDRGainMap:HDRGainMapVersion="65536" '
        b'HDRGainMap:HDRGainMapMin="0.0" '
        b'HDRGainMap:HDRGainMapMax="2.1" '
        b'HDRGainMap:Gamma="1.0" '
        b'HDRGainMap:BaseRenditionIsHDR="False"/>'
        b"</rdf:RDF></x:xmpmeta>"
    )

    meta = GainMapMetadata.from_xmp(apple_xmp)
    assert meta is not None
    assert meta.format_type == "Apple"
    assert abs(meta.gain_map_max[0] - 2.1) < 1e-4
    assert meta.base_rendition_is_hdr is False
    assert abs(meta.hdr_capacity_max - (2.0**2.1)) < 1e-3
    assert abs(meta.max_content_boost - (2.0**2.1)) < 1e-3

    # Export to Apple XMP and parse back
    exported = meta.to_xmp(format_type="Apple")
    parsed_again = GainMapMetadata.from_xmp(exported)
    assert parsed_again is not None
    assert parsed_again.format_type == "Apple"
    assert abs(parsed_again.gain_map_max[0] - 2.1) < 1e-4


def test_gain_map_metadata_iso_xmp_roundtrip() -> None:
    iso_xmp = (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description xmlns:hdrgm="urn:iso:std:iso:ts:21496-1" '
        b'hdrgm:version="1.0.0" '
        b'hdrgm:gainMapMin="-0.5" '
        b'hdrgm:gainMapMax="3.0" '
        b'hdrgm:gamma="1.2" '
        b'hdrgm:offsetSdr="0.015625" '
        b'hdrgm:offsetHdr="0.015625" '
        b'hdrgm:hdrCapacityMin="0.0" '
        b'hdrgm:hdrCapacityMax="3.0" '
        b'hdrgm:baseRenditionIsHDR="False"/>'
        b"</rdf:RDF></x:xmpmeta>"
    )

    meta = GainMapMetadata.from_xmp(iso_xmp)
    assert meta is not None
    assert meta.format_type == "ISO"
    assert abs(meta.gain_map_min[0] - (-0.5)) < 1e-4
    assert abs(meta.gain_map_max[0] - 3.0) < 1e-4
    assert abs(meta.gamma[0] - 1.2) < 1e-4
    assert abs(meta.offset_sdr[0] - 0.015625) < 1e-4
    assert abs(meta.hdr_capacity_max - 3.0) < 1e-4

    # Export to ISO XMP and verify structure
    exported = meta.to_xmp(format_type="ISO")
    assert b"urn:iso:std:iso:ts:21496-1" in exported
    parsed_again = GainMapMetadata.from_xmp(exported)
    assert parsed_again is not None
    assert parsed_again.format_type == "ISO"
    assert abs(parsed_again.gain_map_max[0] - 3.0) < 1e-4


# =====================================================================
# 2. Color Science & Reconstruction Math Tests
# =====================================================================


def test_srgb_eotf_inversion() -> None:
    values = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    linear = srgb_to_linear(values)
    recovered = linear_to_srgb(linear)
    np.testing.assert_allclose(values, recovered, atol=1e-4)


def test_linear_to_pq_monotonicity() -> None:
    linear = np.linspace(0.0, 5.0, 50, dtype=np.float32)
    pq = linear_to_pq(linear)
    assert pq.dtype == np.uint16
    # Non-decreasing
    assert np.all(np.diff(pq.astype(np.int32)) >= 0)
    # Zero input gives zero PQ
    assert pq[0] == 0
    # 1.0 linear corresponds to ~100 nits (~51% in PQ, so around 522 out of 1023)
    assert 500 < pq[10] < 600


def test_resample_gain_map() -> None:
    # 2x2 map to 4x4
    gm = np.array([[0.0, 1.0], [0.5, 1.0]], dtype=np.float32)
    resampled = resample_gain_map(gm, (4, 4))
    assert resampled.shape == (4, 4)
    assert 0.0 <= resampled.min() and resampled.max() <= 1.0
    # Corner (0, 0) should be near 0.0
    assert resampled[0, 0] < 0.2
    # Corner (3, 3) should be 1.0
    assert resampled[3, 3] > 0.8


def test_reconstruct_hdr_boost() -> None:
    # 4x4 SDR image with constant mid-gray (128)
    sdr = np.full((4, 4, 3), 128, dtype=np.uint8)
    # Gain map with 1.0 (indicating 2.0 EV boost, i.e. 4x multiplier)
    gm = np.ones((4, 4), dtype=np.uint8) * 255
    meta = GainMapMetadata(
        gain_map_min=(0.0, 0.0, 0.0),
        gain_map_max=(2.0, 2.0, 2.0),
        gamma=(1.0, 1.0, 1.0),
        hdr_capacity_min=0.0,
        hdr_capacity_max=2.0,
    )

    # Reconstruct with full display boost (4.0)
    hdr_linear = reconstruct_hdr(sdr, gm, meta, display_boost=4.0, output_format="linear_float32")
    assert hdr_linear.shape == (4, 4, 3)
    sdr_linear = srgb_to_linear(128.0 / 255.0)
    expected_linear = (sdr_linear + 0.015625) * 4.0 - 0.015625
    np.testing.assert_allclose(hdr_linear[0, 0, 0], expected_linear, rtol=1e-2)

    # Reconstruct with display_boost=1.0 (SDR display) -> should equal original SDR in linear
    hdr_sdr_linear = reconstruct_hdr(sdr, gm, meta, display_boost=1.0, output_format="linear_float32")
    np.testing.assert_allclose(hdr_sdr_linear[0, 0, 0], sdr_linear, rtol=1e-2)

    # Reconstruct with float16 output
    hdr_fp16 = reconstruct_hdr(sdr, gm, meta, display_boost=4.0, output_format="linear_float16")
    assert hdr_fp16.dtype == np.float16

    # Reconstruct with Rec.2100 PQ uint16 output
    hdr_pq = reconstruct_hdr(sdr, gm, meta, display_boost=4.0, output_format="pq_uint16")
    assert hdr_pq.dtype == np.uint16


# =====================================================================
# 3. C++ assign_auxiliary_image & ISOBMFF Link Tests
# =====================================================================


def test_cpp_assign_auxiliary_image_and_readback(tmp_path: Path) -> None:
    # 1. Create SDR image 64x64 RGB
    sdr_pixels = np.zeros((64, 64, 3), dtype=np.uint8)
    sdr_pixels[:, :, 0] = 200  # reddish
    sdr_img = pylibheif.HeifImage.from_buffer(
        sdr_pixels,
        64,
        64,
        pylibheif.HeifColorspace.RGB,
        pylibheif.HeifChroma.InterleavedRGB,
    )

    # 2. Create Gain Map image 32x32 Monochromatic (L)
    gm_pixels = np.full((32, 32), 180, dtype=np.uint8)
    gm_img = pylibheif.HeifImage.from_buffer(
        gm_pixels,
        32,
        32,
        pylibheif.HeifColorspace.Monochrome,
        pylibheif.HeifChroma.Monochrome,
    )

    # 3. Encode both into context
    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC, preset="ultrafast")

    primary_handle = encoder.encode_image(ctx, sdr_img, preset="ultrafast")
    aux_handle = encoder.encode_image(ctx, gm_img, preset="ultrafast")

    # 4. Assign auxiliary image
    urn = "urn:iso:std:iso:ts:21496-1"
    ctx.assign_auxiliary_image(primary_handle, aux_handle, urn)

    # Add ISO gain map XMP metadata to primary handle
    meta = GainMapMetadata(
        gain_map_min=(0.0, 0.0, 0.0),
        gain_map_max=(2.0, 2.0, 2.0),
        hdr_capacity_max=2.0,
    )
    ctx.add_xmp_metadata(primary_handle, meta.to_xmp("ISO"))

    # Write to memoryview and to file
    out_file = tmp_path / "test_aux.heic"
    ctx.write_to_file(str(out_file))

    # 5. Read back
    read_ctx = pylibheif.HeifContext()
    read_ctx.read_from_file(str(out_file))

    # Top-level image list should only contain primary image (auxiliary image is hidden)
    top_ids = read_ctx.get_list_of_top_level_image_IDs()
    assert len(top_ids) == 1

    read_primary = read_ctx.get_primary_image_handle()
    assert read_primary.width == 64
    assert read_primary.height == 64
    assert read_primary.has_gain_map is True

    # Check auxiliary image handle
    gm_handle = read_primary.get_gain_map_image_handle()
    assert gm_handle is not None
    assert gm_handle.width == 32
    assert gm_handle.height == 32

    # Check gain map metadata extraction on handle
    parsed_meta = read_primary.get_gain_map_metadata()
    assert parsed_meta is not None
    assert parsed_meta.format_type == "ISO"
    assert abs(parsed_meta.gain_map_max[0] - 2.0) < 1e-4

    # Check decode_gain_map convenience method
    decoded_gm = read_primary.decode_gain_map()
    assert decoded_gm.shape[0] == 32
    assert decoded_gm.shape[1] == 32

    # Check reconstruct_hdr on handle
    hdr_reconstructed = read_primary.reconstruct_hdr(display_boost=2.0, output_format="srgb_uint8")
    assert hdr_reconstructed.shape == (64, 64, 3)
    assert hdr_reconstructed.dtype == np.uint8


# =====================================================================
# 4. Pillow Integration Tests
# =====================================================================


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not installed")
def test_pillow_save_and_load_gain_map(tmp_path: Path) -> None:
    # 1. Create Pillow base SDR image
    sdr_pil = Image.new("RGB", (80, 80), color=(180, 100, 50))
    # 2. Create Pillow gain map (half res)
    gm_pil = Image.new("L", (40, 40), color=200)

    meta = GainMapMetadata(
        gain_map_min=(0.0, 0.0, 0.0),
        gain_map_max=(1.5, 1.5, 1.5),
        hdr_capacity_max=1.5,
    )

    out_file = tmp_path / "pillow_gainmap.heic"
    sdr_pil.save(
        out_file,
        format="HEIF",
        gain_map=gm_pil,
        gain_map_metadata=meta,
        preset="ultrafast",
    )

    # 3. Open with Pillow
    opened_im = Image.open(out_file)
    assert isinstance(opened_im, HeifImageFile)
    assert opened_im.has_gain_map is True

    # 4. Extract gain map PIL image
    recovered_gm = opened_im.get_gain_map()
    assert recovered_gm is not None
    assert recovered_gm.size == (40, 40)

    # 5. Check metadata
    assert "gain_map_metadata" in opened_im.info
    assert abs(opened_im.info["gain_map_metadata"].gain_map_max[0] - 1.5) < 1e-4

    # 6. Render HDR
    hdr_pil = opened_im.render_hdr(display_boost=2.0)
    assert isinstance(hdr_pil, Image.Image)
    assert hdr_pil.size == (80, 80)
    assert hdr_pil.mode == "RGB"


# =====================================================================
# 5. CLI Tests
# =====================================================================


def test_cli_info_and_convert_gain_map(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from pylibheif.cli import app

    runner = CliRunner()

    # Create a HEIC with gain map
    sdr_pixels = np.full((64, 64, 3), 128, dtype=np.uint8)
    gm_pixels = np.full((32, 32), 220, dtype=np.uint8)

    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC, preset="ultrafast")
    sdr_img = pylibheif.HeifImage.from_buffer(
        sdr_pixels,
        64,
        64,
        pylibheif.HeifColorspace.RGB,
        pylibheif.HeifChroma.InterleavedRGB,
    )
    gm_img = pylibheif.HeifImage.from_buffer(
        gm_pixels,
        32,
        32,
        pylibheif.HeifColorspace.Monochrome,
        pylibheif.HeifChroma.Monochrome,
    )
    h_sdr = encoder.encode_image(ctx, sdr_img, preset="ultrafast")
    h_gm = encoder.encode_image(ctx, gm_img, preset="ultrafast")
    ctx.assign_auxiliary_image(h_sdr, h_gm, "urn:iso:std:iso:ts:21496-1")

    meta = GainMapMetadata(gain_map_max=(2.0, 2.0, 2.0), hdr_capacity_max=2.0)
    ctx.add_xmp_metadata(h_sdr, meta.to_xmp("ISO"))

    src_heic = tmp_path / "cli_gainmap.heic"
    ctx.write_to_file(str(src_heic))

    # Test 'heic info --json'
    info_res = runner.invoke(app, ["info", str(src_heic), "--json"])
    assert info_res.exit_code == 0
    info_data = json.loads(info_res.stdout)
    assert info_data["has_gain_map"] is True
    assert info_data["gain_map_metadata"] is not None
    assert info_data["gain_map_metadata"]["format_type"] == "ISO"

    # Test 'heic convert --extract-gain-map'
    extracted_gm = tmp_path / "extracted_gm.png"
    target_jpg = tmp_path / "output.jpg"
    convert_res = runner.invoke(
        app,
        [
            "convert",
            str(src_heic),
            str(target_jpg),
            "--extract-gain-map",
            str(extracted_gm),
            "--render-hdr",
            "--hdr-headroom",
            "3.0",
            "-y",
        ],
    )
    assert convert_res.exit_code == 0
    assert target_jpg.exists()
    assert extracted_gm.exists()
