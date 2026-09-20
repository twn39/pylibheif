import io
import os
import pytest
from PIL import Image
import pylibheif
from pylibheif import (
    HeifCompressionFormat,
    HeifContext,
    HeifEncoder,
    AsyncHeifEncoder,
    get_default_encoder_preset,
    set_default_encoder_preset,
)


def test_global_default_encoder_preset():
    orig = get_default_encoder_preset()
    try:
        assert orig == "balanced"
        set_default_encoder_preset("fast")
        assert get_default_encoder_preset() == "fast"
        set_default_encoder_preset("ultrafast")
        assert get_default_encoder_preset() == "ultrafast"
        # Reset with empty string
        set_default_encoder_preset("")
        assert get_default_encoder_preset() == "balanced"
    finally:
        set_default_encoder_preset(orig)


def test_hevc_encoder_presets():
    # Default preset should map to 'medium' for x265 instead of libheif's default 'slow'
    enc = HeifEncoder(HeifCompressionFormat.HEVC)
    if enc.has_parameter("preset"):
        assert enc.get_parameter("preset") == "medium"

    # Explicit ultrafast preset
    enc_ultra = HeifEncoder(HeifCompressionFormat.HEVC, preset="ultrafast")
    if enc_ultra.has_parameter("preset"):
        assert enc_ultra.get_parameter("preset") == "ultrafast"

    # Explicit fast preset
    enc_fast = HeifEncoder(HeifCompressionFormat.HEVC, preset="fast")
    if enc_fast.has_parameter("preset"):
        assert enc_fast.get_parameter("preset") == "fast"

    # Explicit quality preset -> maps to 'slow'
    enc_quality = HeifEncoder(HeifCompressionFormat.HEVC, preset="quality")
    if enc_quality.has_parameter("preset"):
        assert enc_quality.get_parameter("preset") == "slow"


def test_av1_encoder_presets_and_concurrency():
    # AV1 encoder should have speed=6, threads >= 1, and auto-tiles=True by default
    enc = HeifEncoder(HeifCompressionFormat.AV1)
    if enc.has_parameter("speed"):
        assert enc.get_integer_parameter("speed") == 6
    if enc.has_parameter("threads"):
        assert enc.get_integer_parameter("threads") > 0
    if enc.has_parameter("auto-tiles"):
        assert enc.get_boolean_parameter("auto-tiles") is True

    # Check ultrafast maps to speed=8
    enc_ultra = HeifEncoder(HeifCompressionFormat.AV1, preset="ultrafast")
    if enc_ultra.has_parameter("speed"):
        assert enc_ultra.get_integer_parameter("speed") == 8

    # Check quality maps to speed=4
    enc_quality = HeifEncoder(HeifCompressionFormat.AV1, preset="quality")
    if enc_quality.has_parameter("speed"):
        assert enc_quality.get_integer_parameter("speed") == 4


def test_has_parameter_and_set_parameters():
    enc_av1 = HeifEncoder(HeifCompressionFormat.AV1)
    assert enc_av1.has_parameter("speed") is True
    assert enc_av1.has_parameter("non_existent_param_xyz") is False

    # Batch parameters
    enc_av1.set_parameters({"speed": "7", "realtime": "true"})
    assert enc_av1.get_integer_parameter("speed") == 7
    assert enc_av1.get_boolean_parameter("realtime") is True


def test_async_encoder_presets():
    async_enc = AsyncHeifEncoder(HeifCompressionFormat.HEVC, preset="fast")
    if async_enc.has_parameter("preset"):
        assert async_enc.get_parameter("preset") == "fast"

    async_enc.apply_preset("ultrafast")
    if async_enc.has_parameter("preset"):
        assert async_enc.get_parameter("preset") == "ultrafast"


def test_pillow_save_with_presets_and_params():
    pylibheif.register_pillow_opener()

    img = Image.new("RGB", (64, 64), color=(120, 200, 80))

    # 1. Save HEIF with preset
    buf_heif = io.BytesIO()
    img.save(buf_heif, format="HEIF", preset="ultrafast")
    buf_heif.seek(0)
    loaded_heif = Image.open(buf_heif)
    assert loaded_heif.size == (64, 64)
    assert loaded_heif.format in ("HEIF", "HEIC")

    # 2. Save AVIF with speed and threads
    buf_avif = io.BytesIO()
    img.save(buf_avif, format="AVIF", speed=8, threads=4)
    buf_avif.seek(0)
    loaded_avif = Image.open(buf_avif)
    assert loaded_avif.size == (64, 64)

    # 3. Save with arbitrary enc_params
    buf_params = io.BytesIO()
    img.save(buf_params, format="AVIF", enc_params={"speed": "7", "tune": "ssim"})
    assert len(buf_params.getvalue()) > 0

    # 4. Save with quality=-1 (lossless)
    buf_lossless = io.BytesIO()
    img.save(buf_lossless, format="HEIF", quality=-1)
    assert len(buf_lossless.getvalue()) > 0
