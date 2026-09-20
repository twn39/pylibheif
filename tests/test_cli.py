"""Tests for pylibheif CLI (heif / heic / pylibheif)."""

import json
import os
import tempfile
from pathlib import Path
import pytest

typer = pytest.importorskip("typer")
pytest.importorskip("rich")
from typer.testing import CliRunner

from pylibheif.cli import app

runner = CliRunner()
TEST_HEIC = Path(__file__).parent.parent / "images" / "test.heic"


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "info" in result.stdout
    assert "convert" in result.stdout
    assert "doctor" in result.stdout
    assert "metadata" in result.stdout


def test_cli_doctor_json():
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "pylibheif_version" in data
    assert "libheif_version" in data
    assert isinstance(data["encoders"], list)
    assert len(data["encoders"]) > 0
    assert "concurrency" in data
    assert data["concurrency"]["default_encoder_preset"] == "balanced"


def test_cli_doctor_text():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "System Diagnostics" in result.stdout
    assert "libheif Version" in result.stdout


def test_cli_info_json():
    result = runner.invoke(app, ["info", str(TEST_HEIC), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["width"] == 1440
    assert data["height"] == 960
    assert data["has_alpha"] is False
    assert data["bit_depth"] == 8
    assert data["total_images"] >= 1


def test_cli_info_detail():
    result = runner.invoke(app, ["info", str(TEST_HEIC), "--detail", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "metadata_blocks" in data
    assert "image_ids" in data


def test_cli_info_missing_file():
    result = runner.invoke(app, ["info", "non_existent_file_12345.heic"])
    assert result.exit_code != 0


def test_cli_convert_heic_to_avif(tmp_path):
    out_avif = tmp_path / "out.avif"
    result = runner.invoke(
        app,
        [
            "convert",
            str(TEST_HEIC),
            str(out_avif),
            "--preset",
            "ultrafast",
            "--quality",
            "60",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert out_avif.exists()
    assert out_avif.stat().st_size > 0
    data = json.loads(result.stdout)
    assert data["status"] == "success"
    assert data["format"] == "avif"


def test_cli_convert_heic_to_png(tmp_path):
    out_png = tmp_path / "out.png"
    result = runner.invoke(
        app,
        [
            "convert",
            str(TEST_HEIC),
            str(out_png),
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert out_png.exists()
    assert out_png.stat().st_size > 0
    data = json.loads(result.stdout)
    assert data["format"] == "png"


def test_cli_convert_png_to_heic(tmp_path):
    # First convert to PNG
    out_png = tmp_path / "out.png"
    runner.invoke(app, ["convert", str(TEST_HEIC), str(out_png)])

    # Then convert PNG back to HEIC
    out_heic = tmp_path / "from_png.heic"
    result = runner.invoke(
        app,
        [
            "convert",
            str(out_png),
            str(out_heic),
            "--preset",
            "fast",
            "--quality",
            "70",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert out_heic.exists()
    assert out_heic.stat().st_size > 0


def test_cli_convert_overwrite_protection(tmp_path):
    out_file = tmp_path / "target.heic"
    out_file.write_bytes(b"dummy")

    # Without -y / --overwrite, should exit with code 3
    result = runner.invoke(
        app,
        [
            "convert",
            str(TEST_HEIC),
            str(out_file),
        ],
    )
    assert result.exit_code == 3
    assert "already exists" in result.stderr or "already exists" in result.stdout

    # With -y, should overwrite successfully
    result_ow = runner.invoke(
        app,
        [
            "convert",
            str(TEST_HEIC),
            str(out_file),
            "-y",
            "--preset",
            "ultrafast",
        ],
    )
    assert result_ow.exit_code == 0
    assert out_file.stat().st_size > len(b"dummy")


def test_cli_metadata_dump():
    result = runner.invoke(app, ["metadata", "dump", str(TEST_HEIC)])
    assert result.exit_code == 0
    assert "Metadata Blocks" in result.stdout

    result_json = runner.invoke(app, ["metadata", "dump", str(TEST_HEIC), "--json"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.stdout)
    assert "total_blocks" in data
    assert "blocks" in data


def test_cli_info_detail():
    result = runner.invoke(app, ["info", str(TEST_HEIC), "--detail"])
    assert result.exit_code == 0
    assert "Image Information" in result.stdout


def test_cli_info_jpeg_pillow_fallback(tmp_path):
    from PIL import Image, ExifTags

    img_path = tmp_path / "sample.jpg"
    im = Image.new("RGB", (320, 240), color="blue")
    exif = im.getexif()
    exif[ExifTags.Base.Make] = "Nikon"
    exif[ExifTags.Base.Model] = "Z8"
    im.save(str(img_path), format="JPEG", exif=exif)

    # 1. Standard info
    result = runner.invoke(app, ["info", str(img_path)])
    assert result.exit_code == 0
    assert "JPEG" in result.stdout
    assert "Nikon Z8" in result.stdout

    # 2. JSON info
    result_json = runner.invoke(app, ["info", str(img_path), "--json"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.stdout)
    assert data["format"] == "JPEG"
    assert data["width"] == 320
    assert data["height"] == 240
    assert data["shooting_info"]["Camera"] == "Nikon Z8"

    # 3. Metadata dump
    res_dump = runner.invoke(app, ["metadata", "dump", str(img_path)])
    assert res_dump.exit_code == 0
    assert "Metadata Blocks" in res_dump.stdout


def test_cli_info_jpeg_without_pillow(tmp_path):
    import unittest.mock

    img_path = tmp_path / "sample.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIFdummy")

    with unittest.mock.patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
        result = runner.invoke(app, ["info", str(img_path)])
        assert result.exit_code == 1
        assert "requires 'Pillow'" in result.stderr or "requires 'Pillow'" in result.stdout


