"""Command-line interface for pylibheif (heif / heic / pylibheif).

Designed for both interactive command-line use and deterministic AI agent automation.
Supports structured JSON output (--json), cross-format conversion, metadata inspection,
and environment diagnostics.
"""

from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.syntax import Syntax
    from rich.table import Table
except ImportError:
    print(
        "Error: 'typer' and 'rich' are required core dependencies for pylibheif CLI. "
        "Please reinstall via: pip install pylibheif or pip install typer rich",
        file=sys.stderr,
    )
    sys.exit(1)

import pylibheif

app = typer.Typer(
    name="heif",
    help="Fast, modern HEIF/AVIF image toolkit and codec manager for developers and AI agents.",
    no_args_is_help=True,
    add_completion=False,
)

metadata_app = typer.Typer(
    name="metadata",
    help="Inspect, dump, or extract image metadata (EXIF, XMP, ICC profile).",
    no_args_is_help=True,
)
app.add_typer(metadata_app, name="metadata")


def _is_json_mode(json_flag: bool) -> bool:
    """Return True if explicit --json requested or if stdout is redirected in non-interactive pipeline."""
    return json_flag


def _parse_exif_block(raw_bytes: bytes) -> Dict[str, Any]:
    """Parse raw EXIF bytes from libheif into a structured dictionary of human-readable tags."""
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS
        from pylibheif.pillow.metadata import normalize_exif_for_pillow

        norm_exif, _ = normalize_exif_for_pillow(raw_bytes)
        if not norm_exif:
            return {}

        exif = Image.Exif()
        exif.load(norm_exif)

        result: Dict[str, Any] = {}
        # 1. Main tags
        for k, v in exif.items():
            name = TAGS.get(k, f"Tag_{k}")
            if not isinstance(v, bytes):
                result[name] = str(v)

        # 2. Exif Sub-IFD (0x8769)
        try:
            sub_ifd = exif.get_ifd(0x8769)
            for k, v in sub_ifd.items():
                name = TAGS.get(k, f"Tag_{k}")
                if not isinstance(v, bytes):
                    result[name] = str(v)
        except Exception:
            pass

        # 3. GPS IFD (0x8825)
        try:
            gps_ifd = exif.get_ifd(0x8825)
            gps_dict = {}
            for k, v in gps_ifd.items():
                name = GPSTAGS.get(k, f"GPS_{k}")
                if not isinstance(v, bytes):
                    gps_dict[name] = str(v)
            if gps_dict:
                result["GPS"] = gps_dict
        except Exception:
            pass

        return result
    except Exception:
        return {}


def _get_shooting_summary(exif_data: Dict[str, Any]) -> Dict[str, str]:
    """Extract key camera shooting parameters from parsed EXIF."""
    summary: Dict[str, str] = {}
    if not exif_data:
        return summary

    make = exif_data.get("Make", "")
    model = exif_data.get("Model", "")
    lens = exif_data.get("LensModel", "")
    if model:
        dev_str = f"{make} {model}".strip() if (make and make not in model) else model
        if lens and lens != model:
            dev_str += f" ({lens})"
        summary["Camera"] = dev_str

    dt = exif_data.get("DateTimeOriginal") or exif_data.get("DateTime")
    offset = exif_data.get("OffsetTimeOriginal") or exif_data.get("OffsetTime")
    if dt:
        summary["Date Taken"] = f"{dt} {offset}".strip() if offset else dt

    exposure_parts = []
    fl_35 = exif_data.get("FocalLengthIn35mmFilm")
    if fl_35:
        exposure_parts.append(f"{fl_35}mm")
    elif exif_data.get("FocalLength"):
        try:
            exposure_parts.append(f"{float(exif_data['FocalLength']):.1f}mm")
        except Exception:
            pass

    fnum = exif_data.get("FNumber")
    if fnum:
        try:
            exposure_parts.append(f"f/{float(fnum):.1f}")
        except Exception:
            exposure_parts.append(f"f/{fnum}")

    exp_time = exif_data.get("ExposureTime")
    if exp_time:
        try:
            val = float(exp_time)
            if 0 < val < 1.0:
                reciprocal = round(1.0 / val)
                exposure_parts.append(f"1/{reciprocal}s")
            else:
                exposure_parts.append(f"{val:.2f}s")
        except Exception:
            exposure_parts.append(f"{exp_time}s")

    iso = exif_data.get("ISOSpeedRatings")
    if iso:
        exposure_parts.append(f"ISO {iso}")

    if exposure_parts:
        summary["Exposure"] = " · ".join(exposure_parts)

    gps = exif_data.get("GPS")
    if isinstance(gps, dict):
        lat_ref = gps.get("GPS_GPSLatitudeRef", "")
        lat_val = gps.get("GPS_GPSLatitude", "")
        lon_ref = gps.get("GPS_GPSLongitudeRef", "")
        lon_val = gps.get("GPS_GPSLongitude", "")
        alt = gps.get("GPS_GPSAltitude")
        if lat_val and lon_val:
            alt_suffix = ""
            if alt:
                try:
                    alt_suffix = f" (Alt: {float(alt):.1f}m)"
                except Exception:
                    pass
            summary["GPS Location"] = (
                f"{lat_val} {lat_ref}, {lon_val} {lon_ref}{alt_suffix}"
            )

    return summary


def _parse_pillow_exif(im: Any) -> Dict[str, Any]:
    """Parse EXIF tags from a Pillow Image object into a structured dictionary."""
    try:
        from PIL.ExifTags import GPSTAGS, TAGS

        exif = im.getexif()
        if not exif:
            return {}

        result: Dict[str, Any] = {}
        for k, v in exif.items():
            name = TAGS.get(k, f"Tag_{k}")
            if not isinstance(v, bytes):
                result[name] = str(v)

        try:
            sub_ifd = exif.get_ifd(0x8769)
            for k, v in sub_ifd.items():
                name = TAGS.get(k, f"Tag_{k}")
                if not isinstance(v, bytes):
                    result[name] = str(v)
        except Exception:
            pass

        try:
            gps_ifd = exif.get_ifd(0x8825)
            gps_dict = {}
            for k, v in gps_ifd.items():
                name = GPSTAGS.get(k, f"GPS_{k}")
                if not isinstance(v, bytes):
                    gps_dict[name] = str(v)
            if gps_dict:
                result["GPS"] = gps_dict
        except Exception:
            pass

        return result
    except Exception:
        return {}


def _info_cmd_pillow(file: Path, json_output: bool, detail: bool) -> None:
    """Inspect standard non-HEIF images (JPEG, PNG, etc.) via Pillow fallback."""
    from PIL import Image

    try:
        im = Image.open(str(file))
    except Exception as e:
        typer.echo(f"Error opening image '{file}': {e}", err=True)
        raise typer.Exit(code=1)

    width, height = im.size
    mode = im.mode
    fmt = (im.format or file.suffix.lstrip(".")).upper()
    file_size = file.stat().st_size
    has_alpha = mode in ("RGBA", "LA", "PA") or "transparency" in im.info
    bit_depth = 16 if "16" in mode else 8
    has_icc = "icc_profile" in im.info
    color_profile_type = "ICC" if has_icc else "NotPresent"

    # EXIF and XMP
    parsed_exif = _parse_pillow_exif(im)
    has_exif = bool(parsed_exif)

    xmp_text: Optional[str] = None
    if "xmp" in im.info:
        raw = im.info["xmp"]
        xmp_text = (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else str(raw)
        )
    elif "XML:com.adobe.xmp" in im.info:
        raw = im.info["XML:com.adobe.xmp"]
        xmp_text = (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else str(raw)
        )
    has_xmp = bool(xmp_text)

    shooting_summary = _get_shooting_summary(parsed_exif)

    meta_blocks: List[Dict[str, Any]] = []
    if parsed_exif:
        meta_blocks.append(
            {
                "id": 1,
                "type": "Exif",
                "size_bytes": len(im.info.get("exif", b"")),
                "parsed_exif": parsed_exif,
            }
        )
    if xmp_text:
        meta_blocks.append(
            {
                "id": 2,
                "type": "mime",
                "size_bytes": len(xmp_text.encode("utf-8")),
                "content_utf8": xmp_text,
            }
        )
    if has_icc:
        meta_blocks.append(
            {
                "id": 3,
                "type": "icc",
                "size_bytes": len(im.info["icc_profile"]),
            }
        )

    data: Dict[str, Any] = {
        "file": str(file.resolve()),
        "format": fmt,
        "size_bytes": file_size,
        "width": width,
        "height": height,
        "has_alpha": has_alpha,
        "bit_depth": bit_depth,
        "color_mode": mode,
        "total_images": 1,
        "color_profile": {
            "type": color_profile_type,
            "has_icc": has_icc,
            "has_nclx": False,
        },
        "metadata_summary": {
            "has_exif": has_exif,
            "has_xmp": has_xmp,
            "total_blocks": len(meta_blocks),
        },
        "hdr": None,
    }

    if shooting_summary:
        data["shooting_info"] = shooting_summary
    if parsed_exif:
        data["exif"] = parsed_exif
    if xmp_text:
        data["xmp_preview"] = xmp_text

    if detail:
        data["metadata_blocks"] = meta_blocks

    if _is_json_mode(json_output):
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    console = Console()
    table = Table(
        title=f"Image Information: [bold cyan]{file.name}[/bold cyan] ({fmt})"
    )
    table.add_column("Property", style="bold yellow")
    table.add_column("Value", style="green")

    table.add_row("Format", fmt)
    table.add_row("Resolution", f"{width} x {height}")
    table.add_row("Color Mode", f"{mode} ({bit_depth}-bit)")
    table.add_row("Alpha Channel", "Yes" if has_alpha else "No")
    table.add_row("File Size", f"{file_size / 1024:.1f} KB ({file_size} bytes)")
    table.add_row("Color Profile", color_profile_type)

    if shooting_summary:
        if "Camera" in shooting_summary:
            table.add_row("Camera / Device", shooting_summary["Camera"])
        if "Date Taken" in shooting_summary:
            table.add_row("Date Taken", shooting_summary["Date Taken"])
        if "Exposure" in shooting_summary:
            table.add_row("Exposure", shooting_summary["Exposure"])
        if "GPS Location" in shooting_summary:
            table.add_row("GPS Location", shooting_summary["GPS Location"])

    table.add_row(
        "Metadata",
        f"EXIF: {'Yes' if has_exif else 'No'} | XMP: {'Yes' if has_xmp else 'No'} | Blocks: {len(meta_blocks)}",
    )
    console.print(table)

    if detail:
        if parsed_exif:
            exif_table = Table(title=f"EXIF Tags: [bold cyan]{file.name}[/bold cyan]")
            exif_table.add_column("Tag Name", style="cyan")
            exif_table.add_column("Value", style="green")
            for k, v in sorted(parsed_exif.items()):
                if k != "GPS":
                    exif_table.add_row(str(k), str(v))
            console.print(exif_table)

        if xmp_text:
            console.print(
                Panel(
                    Syntax(
                        xmp_text.strip(),
                        "xml",
                        theme="monokai",
                        line_numbers=True,
                        word_wrap=True,
                    ),
                    title=f"XMP / MIME Metadata: [bold cyan]{file.name}[/bold cyan]",
                )
            )


def _metadata_dump_pillow(file: Path, json_output: bool) -> None:
    """Dump metadata from standard non-HEIF images (JPEG, PNG, etc.) via Pillow fallback."""
    from PIL import Image

    try:
        im = Image.open(str(file))
    except Exception as e:
        typer.echo(f"Error reading file '{file}': {e}", err=True)
        raise typer.Exit(code=1)

    parsed_exif = _parse_pillow_exif(im)
    xmp_text: Optional[str] = None
    if "xmp" in im.info:
        raw = im.info["xmp"]
        xmp_text = (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else str(raw)
        )
    elif "XML:com.adobe.xmp" in im.info:
        raw = im.info["XML:com.adobe.xmp"]
        xmp_text = (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else str(raw)
        )

    blocks: List[Dict[str, Any]] = []
    block_id = 1
    if parsed_exif:
        blocks.append(
            {
                "id": block_id,
                "type": "Exif",
                "size_bytes": len(im.info.get("exif", b"")),
                "parsed_exif": parsed_exif,
            }
        )
        block_id += 1
    if xmp_text:
        blocks.append(
            {
                "id": block_id,
                "type": "mime",
                "size_bytes": len(xmp_text.encode("utf-8")),
                "content_utf8": xmp_text,
            }
        )
        block_id += 1
    if "icc_profile" in im.info:
        blocks.append(
            {
                "id": block_id,
                "type": "icc",
                "size_bytes": len(im.info["icc_profile"]),
            }
        )
        block_id += 1

    out_data = {
        "file": str(file.resolve()),
        "total_blocks": len(blocks),
        "blocks": blocks,
    }

    if _is_json_mode(json_output):
        print(json.dumps(out_data, indent=2, ensure_ascii=False))
        return

    console = Console()
    table = Table(title=f"Metadata Blocks: [bold cyan]{file.name}[/bold cyan]")
    table.add_column("Block ID", justify="right", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Size (Bytes)", justify="right", style="green")

    for b in blocks:
        table.add_row(str(b["id"]), b["type"], str(b["size_bytes"]))

    if not blocks:
        console.print(f"[dim]No metadata blocks found in '{file.name}'.[/dim]")
        return

    console.print(table)

    for b in blocks:
        mtype = b["type"].lower()
        if mtype == "exif" and b.get("parsed_exif"):
            exif_table = Table(
                title=f"EXIF Tags: [bold cyan]{file.name}[/bold cyan] (Block {b['id']})"
            )
            exif_table.add_column("Tag Name", style="cyan")
            exif_table.add_column("Value", style="green")
            for k, v in sorted(b["parsed_exif"].items()):
                if k != "GPS":
                    exif_table.add_row(str(k), str(v))
            console.print(exif_table)

            if "GPS" in b["parsed_exif"] and isinstance(b["parsed_exif"]["GPS"], dict):
                gps_table = Table(title=f"GPS Information (Block {b['id']})")
                gps_table.add_column("GPS Tag", style="cyan")
                gps_table.add_column("Value", style="green")
                for k, v in sorted(b["parsed_exif"]["GPS"].items()):
                    gps_table.add_row(str(k), str(v))
                console.print(gps_table)

        elif (mtype in ("mime", "xmp") or "xml" in mtype) and b.get("content_utf8"):
            console.print(
                Panel(
                    Syntax(
                        b["content_utf8"].strip(),
                        "xml",
                        theme="monokai",
                        line_numbers=True,
                        word_wrap=True,
                    ),
                    title=f"XMP / MIME Metadata: [bold cyan]{file.name}[/bold cyan] (Block {b['id']})",
                )
            )


def _metadata_extract_pillow(file: Path, out_file: Path, meta_type: str) -> None:
    """Extract metadata binary from non-HEIF image via Pillow."""
    from PIL import Image

    try:
        im = Image.open(str(file))
    except Exception as e:
        typer.echo(f"Error opening image '{file}': {e}", err=True)
        raise typer.Exit(code=1)

    raw_data = b""
    meta_type_lower = meta_type.lower()
    if "exif" in meta_type_lower:
        raw_data = im.info.get("exif", b"")
    elif "xmp" in meta_type_lower or "mime" in meta_type_lower:
        xmp = im.info.get("xmp") or im.info.get("XML:com.adobe.xmp")
        if isinstance(xmp, str):
            raw_data = xmp.encode("utf-8")
        elif isinstance(xmp, bytes):
            raw_data = xmp
    elif "icc" in meta_type_lower:
        raw_data = im.info.get("icc_profile", b"")

    if not raw_data:
        typer.echo(
            f"Error: No metadata of type '{meta_type}' found in '{file.name}'.",
            err=True,
        )
        raise typer.Exit(code=1)

    out_file.write_bytes(raw_data)
    typer.echo(
        f"Successfully extracted {len(raw_data)} bytes of '{meta_type}' metadata to '{out_file}'."
    )


# =====================================================================
# 1. info command
# =====================================================================
def _info_single_file(file: Path, json_output: bool, detail: bool) -> None:
    """Inspect a single image file dimensions, channels, bit depth, color profile, and HDR metadata."""
    try:
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(str(file))
        handle = ctx.get_primary_image_handle()
    except Exception:
        # Fallback to Pillow for non-HEIF formats (JPEG, PNG, etc.)
        if importlib.util.find_spec("PIL") is None:
            typer.echo(
                f"Error: '{file.name}' is not a HEIF/AVIF image. "
                f"Inspecting non-HEIF formats (JPEG, PNG, etc.) requires 'Pillow'.\n"
                f"Please install it via: pip install 'pylibheif[pillow]' or pip install pillow",
                err=True,
            )
            raise typer.Exit(code=1)

        _info_cmd_pillow(file, json_output, detail)
        return

    image_ids = ctx.get_list_of_top_level_image_IDs()
    primary_id = image_ids[0] if image_ids else 0

    # Collect metadata blocks and parsed previews
    meta_blocks: List[Dict[str, Any]] = []
    has_exif = False
    has_xmp = False
    parsed_exif: Dict[str, Any] = {}
    xmp_text: Optional[str] = None

    for mid in handle.get_metadata_block_ids():
        mtype = handle.get_metadata_block_type(mid)
        mdata = handle.get_metadata_block(mid)
        b_info: Dict[str, Any] = {"id": mid, "type": mtype, "size_bytes": len(mdata)}
        if mtype.lower() == "exif":
            has_exif = True
            if not parsed_exif:
                parsed_exif = _parse_exif_block(mdata)
            b_info["parsed_exif"] = parsed_exif
        elif mtype.lower() in ("mime", "xmp") or "xml" in mtype.lower():
            has_xmp = True
            try:
                xmp_text = mdata.decode("utf-8", errors="replace")
                b_info["content_utf8"] = xmp_text
            except Exception:
                pass
        meta_blocks.append(b_info)

    shooting_summary = _get_shooting_summary(parsed_exif)

    # Color profile
    color_profile_type = str(handle.color_profile_type).split(".")[-1]
    has_icc = color_profile_type == "Prof"
    has_nclx = color_profile_type == "Nclx"
    nclx_details: Optional[Dict[str, Any]] = None
    if has_nclx:
        nclx = handle.get_nclx_color_profile()
        if nclx:
            nclx_details = {
                "color_primaries": int(nclx.color_primaries.value),
                "transfer_characteristics": int(nclx.transfer_characteristics.value),
                "matrix_coefficients": int(nclx.matrix_coefficients.value),
                "full_range_flag": bool(nclx.full_range_flag),
            }

    color_info: Dict[str, Any] = {}
    try:
        if hasattr(handle, "get_color_profile_info"):
            color_info = handle.get_color_profile_info()
    except Exception:
        pass

    # HDR Metadata
    hdr_info: Dict[str, Any] = {}
    if getattr(handle, "has_content_light_level", False):
        try:
            clli = getattr(handle, "content_light_level", None)
            if clli is None:
                getter = getattr(handle, "get_content_light_level", None)
                if callable(getter):
                    clli = getter()
            if clli:
                hdr_info["clli"] = {
                    "max_content_light_level": clli.max_content_light_level,
                    "max_pic_average_light_level": clli.max_pic_average_light_level,
                }
        except Exception:
            pass

    if getattr(handle, "has_mastering_display_colour_volume", False):
        try:
            mdcv = getattr(handle, "mastering_display_colour_volume", None)
            if mdcv is None:
                getter = getattr(handle, "get_mastering_display_colour_volume", None)
                if callable(getter):
                    mdcv = getter()
            if mdcv:
                hdr_info["mdcv"] = {
                    "display_primaries_x": [
                        mdcv.display_primaries_x[0],
                        mdcv.display_primaries_x[1],
                        mdcv.display_primaries_x[2],
                    ],
                    "display_primaries_y": [
                        mdcv.display_primaries_y[0],
                        mdcv.display_primaries_y[1],
                        mdcv.display_primaries_y[2],
                    ],
                    "white_point_x": mdcv.white_point_x,
                    "white_point_y": mdcv.white_point_y,
                    "max_luminance": mdcv.max_display_mastering_luminance,
                    "min_luminance": mdcv.min_display_mastering_luminance,
                }
        except Exception:
            pass

    if getattr(handle, "has_ambient_viewing_environment", False):
        try:
            amve = getattr(handle, "ambient_viewing_environment", None)
            if amve is None:
                getter = getattr(handle, "get_ambient_viewing_environment", None)
                if callable(getter):
                    amve = getter()
            if amve:
                hdr_info["amve"] = {
                    "ambient_illumination": amve.ambient_illumination,
                    "ambient_light": amve.ambient_light,
                }
        except Exception:
            pass

    # Gain Map Details
    gm_meta_dict: Optional[Dict[str, Any]] = None
    if handle.has_gain_map:
        try:
            gm_meta = handle.get_gain_map_metadata()
            if gm_meta:
                gm_meta_dict = gm_meta.to_dict()
        except Exception:
            pass

    data: Dict[str, Any] = {
        "file": str(file.resolve()),
        "size_bytes": os.path.getsize(file),
        "width": handle.width,
        "height": handle.height,
        "has_alpha": handle.has_alpha,
        "bit_depth": handle.luma_bits_per_pixel,
        "chroma_bits_per_pixel": handle.chroma_bits_per_pixel,
        "total_images": len(image_ids),
        "primary_image_id": primary_id,
        "thumbnails_count": handle.number_of_thumbnails,
        "has_depth_image": handle.has_depth_image,
        "has_gain_map": handle.has_gain_map,
        "gain_map_metadata": gm_meta_dict,
        "color_profile": {
            "type": color_profile_type,
            "has_icc": has_icc,
            "has_nclx": has_nclx,
            **({"nclx": nclx_details} if (detail and nclx_details) else {}),
            **({"info": color_info} if color_info else {}),
        },
        "metadata_summary": {
            "has_exif": has_exif,
            "has_xmp": has_xmp,
            "total_blocks": len(meta_blocks),
        },
        "hdr": hdr_info or None,
    }

    if shooting_summary:
        data["shooting_info"] = shooting_summary
    if parsed_exif:
        data["exif"] = parsed_exif
    if xmp_text:
        data["xmp_preview"] = xmp_text

    if detail:
        data["metadata_blocks"] = meta_blocks
        data["image_ids"] = image_ids

    if _is_json_mode(json_output):
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    console = Console()
    table = Table(
        title=f"Image Information: [bold cyan]{file.name}[/bold cyan] (HEIF/AVIF)"
    )
    table.add_column("Property", style="bold yellow")
    table.add_column("Value", style="green")

    table.add_row("Resolution", f"{handle.width} x {handle.height}")
    table.add_row("Alpha Channel", "Yes" if handle.has_alpha else "No")
    table.add_row("Bit Depth", f"{handle.luma_bits_per_pixel}-bit (Luma)")
    table.add_row("Total Images", f"{len(image_ids)} (Primary ID: {primary_id})")
    table.add_row("Thumbnails", str(handle.number_of_thumbnails))
    file_size = os.path.getsize(file)
    table.add_row("File Size", f"{file_size / 1024:.1f} KB ({file_size} bytes)")
    table.add_row(
        "Auxiliary Images",
        f"Depth: {'Yes' if handle.has_depth_image else 'No'} | Gain Map: {'Yes' if handle.has_gain_map else 'No'}",
    )

    prof_str = f"Type: {color_profile_type}"
    if has_nclx and nclx_details:
        prof_str += f" | Primaries: {nclx_details['color_primaries']}, Transfer: {nclx_details['transfer_characteristics']}"
    elif has_icc:
        desc = (
            color_info.get("description")
            or color_info.get("model")
            or color_info.get("name")
        )
        if desc:
            prof_str += f" ({desc})"
    table.add_row("Color Profile", prof_str)

    if shooting_summary:
        if "Camera" in shooting_summary:
            table.add_row("Camera / Device", shooting_summary["Camera"])
        if "Date Taken" in shooting_summary:
            table.add_row("Date Taken", shooting_summary["Date Taken"])
        if "Exposure" in shooting_summary:
            table.add_row("Exposure", shooting_summary["Exposure"])
        if "GPS Location" in shooting_summary:
            table.add_row("GPS Location", shooting_summary["GPS Location"])

    table.add_row(
        "Metadata Blocks",
        f"EXIF: {'Yes' if has_exif else 'No'} | XMP: {'Yes' if has_xmp else 'No'} | Total: {len(meta_blocks)}",
    )

    if hdr_info:
        hdr_desc = []
        if "clli" in hdr_info:
            hdr_desc.append(
                f"CLLI (Max: {hdr_info['clli']['max_content_light_level']} nits, Avg: {hdr_info['clli']['max_pic_average_light_level']} nits)"
            )
        if "mdcv" in hdr_info:
            hdr_desc.append(f"MDCV ({hdr_info['mdcv']['max_luminance']} nits)")
        if "amve" in hdr_info:
            hdr_desc.append(f"AMVE ({hdr_info['amve']['ambient_illumination']} lux)")
        table.add_row("HDR Metadata", ", ".join(hdr_desc))

    console.print(table)

    if detail:
        if parsed_exif:
            exif_table = Table(title=f"EXIF Tags: [bold cyan]{file.name}[/bold cyan]")
            exif_table.add_column("Tag Name", style="cyan")
            exif_table.add_column("Value", style="green")
            for k, v in sorted(parsed_exif.items()):
                if k != "GPS":
                    exif_table.add_row(str(k), str(v))
            console.print(exif_table)

        if xmp_text:
            console.print(
                Panel(
                    Syntax(
                        xmp_text.strip(),
                        "xml",
                        theme="monokai",
                        line_numbers=True,
                        word_wrap=True,
                    ),
                    title=f"XMP / MIME Metadata: [bold cyan]{file.name}[/bold cyan]",
                )
            )


def _get_file_info_data(file: Path, detail: bool = False) -> Dict[str, Any]:
    """Lightweight extractor of structured image properties."""
    try:
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(str(file))
        handle = ctx.get_primary_image_handle()
        image_ids = ctx.get_list_of_top_level_image_IDs()
        color_profile_type = str(handle.color_profile_type).split(".")[-1]
        has_icc = color_profile_type == "Prof"
        has_nclx = color_profile_type == "Nclx"
        color_info: Dict[str, Any] = {}
        try:
            if hasattr(handle, "get_color_profile_info"):
                color_info = handle.get_color_profile_info()
        except Exception:
            pass

        return {
            "file": str(file.resolve()),
            "format": "HEIF",
            "width": handle.width,
            "height": handle.height,
            "has_alpha": handle.has_alpha,
            "bit_depth": handle.luma_bits_per_pixel,
            "channels": 4 if handle.has_alpha else 3,
            "total_images": len(image_ids),
            "has_gain_map": handle.has_gain_map,
            "color_profile": {
                "type": color_profile_type,
                "has_icc": has_icc,
                "has_nclx": has_nclx,
                "info": color_info,
            },
            "size_bytes": os.path.getsize(file),
        }
    except Exception:
        pass

    try:
        from PIL import Image

        with Image.open(str(file)) as im:
            return {
                "file": str(file.resolve()),
                "format": im.format or file.suffix.lstrip(".").upper(),
                "width": im.width,
                "height": im.height,
                "has_alpha": "A" in im.mode,
                "bit_depth": 8,
                "channels": len(im.getbands()),
                "total_images": 1,
                "has_gain_map": False,
                "color_profile": {
                    "type": "ICC" if "icc_profile" in im.info else "sRGB",
                    "has_icc": "icc_profile" in im.info,
                    "has_nclx": False,
                },
                "size_bytes": os.path.getsize(file),
            }
    except Exception as e:
        return {
            "file": str(file.resolve()),
            "error": str(e),
        }


@app.command(
    "info",
    help="Inspect image dimensions, color profiles, HDR tags, and metadata (single file or batch).",
)
def info_cmd(
    files: List[Path] = typer.Argument(
        ...,
        help="Path to image file(s) or directory",
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output machine-readable JSON format"
    ),
    detail: bool = typer.Option(
        False,
        "--detail",
        "-d",
        help="Include detailed ICC/NCLX and metadata blocks",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Recursively discover images in directories",
    ),
) -> None:
    """Inspect image dimensions, channels, bit depth, color profile, and HDR metadata."""
    if len(files) == 1 and not files[0].is_dir():
        f = files[0]
        if not f.exists():
            typer.echo(
                f"Error: Invalid value for 'FILES...': Path '{f}' does not exist.",
                err=True,
            )
            raise typer.Exit(code=2)
        _info_single_file(f, json_output, detail)
        return

    # Multi-file or directory mode
    valid_exts = {
        ".heic",
        ".heif",
        ".avif",
        ".hif",
        ".jpeg",
        ".jpg",
        ".png",
        ".webp",
        ".bmp",
        ".tiff",
        ".tif",
        ".jp2",
    }
    discovered: List[Path] = []
    for item in files:
        if not item.exists():
            typer.echo(
                f"Warning: File or directory '{item}' does not exist.",
                err=True,
            )
            continue
        if item.is_file():
            discovered.append(item)
        elif item.is_dir():
            pattern = "**/*" if recursive else "*"
            for p in sorted(item.glob(pattern)):
                if p.is_file() and p.suffix.lower() in valid_exts:
                    discovered.append(p)

    if not discovered:
        typer.echo("Error: No matching image files found.", err=True)
        raise typer.Exit(code=1)

    if _is_json_mode(json_output):
        results = [_get_file_info_data(f, detail=detail) for f in discovered]
        print(json.dumps(results, indent=2))
    else:
        console = Console()
        table = Table(
            title=f"Image Library Inspection ({len(discovered)} images)",
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("File", style="bold", no_wrap=True)
        table.add_column("Dimensions", justify="right")
        table.add_column("Format")
        table.add_column("Bit Depth", justify="center")
        table.add_column("Channels", justify="center")
        table.add_column("Color Profile")
        table.add_column("HDR / Gain Map", justify="center")
        table.add_column("Size", justify="right")

        total_bytes = 0
        for f in discovered:
            try:
                sz = f.stat().st_size
                total_bytes += sz
                info = _get_file_info_data(f, detail=False)
                dims = f"{info.get('width', '?')}x{info.get('height', '?')}"
                fmt = info.get("format", f.suffix.lstrip(".").upper())
                depth = f"{info.get('bit_depth', 8)}-bit"
                channels = str(info.get("channels", "3"))
                profile = str(info.get("color_profile", {}).get("type", "sRGB"))
                hdr_status = (
                    "[bold green]Gain Map[/bold green]"
                    if info.get("has_gain_map")
                    else ("[cyan]HDR10[/cyan]" if info.get("hdr") else "SDR")
                )
                size_str = (
                    f"{sz / 1024 / 1024:.2f} MB"
                    if sz >= 1024 * 1024
                    else f"{sz / 1024:.1f} KB"
                )
                table.add_row(
                    f.name,
                    dims,
                    fmt,
                    depth,
                    channels,
                    profile,
                    hdr_status,
                    size_str,
                )
            except Exception as e:
                table.add_row(f.name, "Error", "-", "-", "-", "-", "-", str(e))

        console.print(table)
        total_size_mb = total_bytes / (1024 * 1024)
        console.print(
            f"[dim]Total: {len(discovered)} images, {total_size_mb:.2f} MB[/dim]"
        )


# =====================================================================
# 2. convert command


def _convert_single_file(
    source: Path,
    target: Path,
    format: Optional[str] = None,
    quality: int = 80,
    preset: str = "balanced",
    lossless: bool = False,
    threads: int = 0,
    extract_gain_map: Optional[Path] = None,
    render_hdr: bool = False,
    hdr_headroom: Optional[float] = None,
    strip_metadata: bool = False,
    to_srgb: bool = False,
    intent: str = "perceptual",
    overwrite: bool = False,
    skip_existing: bool = False,
) -> Dict[str, Any]:
    if target.exists():
        if skip_existing:
            return {
                "status": "skipped",
                "source": str(source.resolve()),
                "target": str(target.resolve()),
                "reason": "Target file already exists",
            }
        if not overwrite:
            return {
                "status": "failed",
                "source": str(source.resolve()),
                "target": str(target.resolve()),
                "error": f"Error: Target file '{target}' already exists. Use --overwrite / -y to replace.",
                "exit_code": 3,
            }

    # Resolve target format
    tgt_ext = target.suffix.lower()
    fmt_str = (format.lower() if format else tgt_ext.lstrip(".")).lower()
    if fmt_str in ("jpg", "jpeg"):
        target_fmt = "jpeg"
    elif fmt_str in ("heic", "heif"):
        target_fmt = "heic"
    elif fmt_str == "avif":
        target_fmt = "avif"
    elif fmt_str == "png":
        target_fmt = "png"
    else:
        return {
            "status": "failed",
            "source": str(source.resolve()),
            "target": str(target.resolve()),
            "error": f"Error: Unsupported target format '{fmt_str}'. Expected: heic, avif, jpeg, png.",
            "exit_code": 2,
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    src_ext = source.suffix.lower()
    is_source_heif = src_ext in (".heic", ".heif", ".avif", ".hif")

    try:
        # 1. Source is HEIF/AVIF
        if is_source_heif:
            ctx = pylibheif.HeifContext()
            ctx.read_from_file(str(source))
            handle = ctx.get_primary_image_handle()

            # Handle gain map extraction if requested
            if extract_gain_map is not None:
                if handle.has_gain_map:
                    try:
                        from pylibheif.pillow import to_pillow

                        gm_handle = handle.get_gain_map_image_handle()
                        gm_pil = to_pillow(gm_handle)
                        extract_gain_map.parent.mkdir(parents=True, exist_ok=True)
                        gm_pil.save(str(extract_gain_map))
                        typer.echo(
                            f"Extracted auxiliary Gain Map to '{extract_gain_map}'."
                        )
                    except Exception as e:
                        typer.echo(
                            f"Warning: Failed to extract gain map: {e}", err=True
                        )
                else:
                    typer.echo(
                        f"Warning: '{source.name}' does not contain an auxiliary Gain Map.",
                        err=True,
                    )

            # Target is HEIF or AVIF
            if target_fmt in ("heic", "avif"):
                comp_fmt = (
                    pylibheif.HeifCompressionFormat.HEVC
                    if target_fmt == "heic"
                    else pylibheif.HeifCompressionFormat.AV1
                )
                encoder = pylibheif.HeifEncoder(comp_fmt, preset=preset)
                encoder.set_lossless(lossless)
                if not lossless:
                    encoder.set_lossy_quality(quality)

                out_ctx = pylibheif.HeifContext()

                if render_hdr and handle.has_gain_map:
                    hdr_arr = handle.reconstruct_hdr(
                        display_boost=hdr_headroom, output_format="srgb_uint8"
                    )
                    raw_img = pylibheif.HeifImage.from_buffer(
                        hdr_arr,
                        hdr_arr.shape[1],
                        hdr_arr.shape[0],
                        pylibheif.HeifColorspace.RGB,
                        pylibheif.HeifChroma.InterleavedRGB,
                    )
                else:
                    decode_opts = pylibheif.HeifDecodingOptions()
                    if threads > 0:
                        decode_opts.num_codec_threads = threads
                    raw_img = handle.decode(
                        pylibheif.HeifColorspace.RGB,
                        pylibheif.HeifChroma.InterleavedRGB,
                        options=decode_opts,
                        target_colorspace="sRGB" if to_srgb else None,
                        intent=intent,
                    )

                out_handle = encoder.encode_image(out_ctx, raw_img, preset=preset)

                if handle.has_gain_map and not render_hdr and not strip_metadata:
                    try:
                        gm_img = handle.decode_gain_map()
                        aux_encoder = pylibheif.HeifEncoder(comp_fmt, preset=preset)
                        aux_handle = aux_encoder.encode_image(
                            out_ctx, gm_img, preset=preset
                        )
                        gm_meta = handle.get_gain_map_metadata()
                        urn = "urn:iso:std:iso:ts:21496-1"
                        if gm_meta and gm_meta.format_type == "Apple":
                            urn = "urn:com:apple:photo:2020:aux:hdrgainmap"
                        out_ctx.assign_auxiliary_image(out_handle, aux_handle, urn)
                    except Exception:
                        pass

                if not strip_metadata:
                    for mid in handle.get_metadata_block_ids():
                        mtype = handle.get_metadata_block_type(mid)
                        mdata = handle.get_metadata_block(mid)
                        try:
                            if mtype.lower() == "exif":
                                out_ctx.add_exif_metadata(out_handle, mdata)
                            elif mtype.lower() in ("xmp", "mime"):
                                out_ctx.add_xmp_metadata(out_handle, mdata)
                        except Exception:
                            pass

                out_ctx.write_to_file(str(target))

            else:
                try:
                    from PIL import Image
                    from pylibheif.pillow import to_pillow
                except ImportError:
                    return {
                        "status": "failed",
                        "source": str(source.resolve()),
                        "target": str(target.resolve()),
                        "error": "Error: Converting to PNG/JPEG requires 'Pillow'. Install via: pip install 'pylibheif[pillow]'",
                        "exit_code": 2,
                    }

                if render_hdr and handle.has_gain_map:
                    hdr_arr = handle.reconstruct_hdr(
                        display_boost=hdr_headroom, output_format="srgb_uint8"
                    )
                    pil_img = Image.fromarray(hdr_arr)
                else:
                    pil_img = to_pillow(
                        handle,
                        target_colorspace="sRGB" if to_srgb else None,
                        intent=intent,
                    )

                save_kwargs: Dict[str, Any] = {}
                if target_fmt == "jpeg":
                    save_kwargs["quality"] = quality
                    if pil_img.mode in ("RGBA", "P"):
                        pil_img = pil_img.convert("RGB")
                pil_img.save(str(target), **save_kwargs)

        # 2. Source is standard image (PNG, JPEG, etc.)
        else:
            try:
                from PIL import Image
                from pylibheif.pillow import from_pillow
            except ImportError:
                return {
                    "status": "failed",
                    "source": str(source.resolve()),
                    "target": str(target.resolve()),
                    "error": "Error: Converting from PNG/JPEG requires 'Pillow'. Install via: pip install 'pylibheif[pillow]'",
                    "exit_code": 2,
                }

            with Image.open(source) as pil_img:
                if to_srgb:
                    from pylibheif.color import transform_colorspace

                    src_icc = pil_img.info.get("icc_profile")
                    if src_icc:
                        res = transform_colorspace(
                            pil_img,
                            src_profile=src_icc,
                            dst_profile="sRGB",
                            intent=intent,
                            as_pillow=True,
                        )
                        if isinstance(res, Image.Image):
                            pil_img = res

                if target_fmt in ("heic", "avif"):
                    comp_fmt = (
                        pylibheif.HeifCompressionFormat.HEVC
                        if target_fmt == "heic"
                        else pylibheif.HeifCompressionFormat.AV1
                    )
                    encoder = pylibheif.HeifEncoder(comp_fmt, preset=preset)
                    encoder.set_lossless(lossless)
                    if not lossless:
                        encoder.set_lossy_quality(quality)

                    heif_img, _ = from_pillow(pil_img)
                    out_ctx = pylibheif.HeifContext()
                    encoder.encode_image(out_ctx, heif_img, preset=preset)
                    out_ctx.write_to_file(str(target))
                else:
                    if target_fmt == "jpeg":
                        if pil_img.mode in ("RGBA", "P"):
                            pil_img = pil_img.convert("RGB")
                        pil_img.save(str(target), quality=quality)
                    else:
                        pil_img.save(str(target))

    except Exception as e:
        return {
            "status": "failed",
            "source": str(source.resolve()),
            "target": str(target.resolve()),
            "error": f"Conversion failed: {e}",
            "exit_code": 1,
        }

    t1 = time.perf_counter()
    return {
        "status": "success",
        "source": str(source.resolve()),
        "target": str(target.resolve()),
        "format": target_fmt,
        "quality": quality,
        "preset": preset,
        "lossless": lossless,
        "to_srgb": to_srgb,
        "intent": intent if to_srgb else None,
        "target_size_bytes": os.path.getsize(target),
        "source_size_bytes": os.path.getsize(source),
        "duration_ms": round((t1 - t0) * 1000, 2),
    }


def _batch_convert_worker(args: Tuple[Any, ...]) -> Dict[str, Any]:
    (
        src,
        tgt,
        fmt,
        quality,
        preset,
        lossless,
        threads,
        extract_gain_map,
        render_hdr,
        hdr_headroom,
        strip_metadata,
        to_srgb,
        intent,
        overwrite,
        skip_existing,
    ) = args
    return _convert_single_file(
        source=src,
        target=tgt,
        format=fmt,
        quality=quality,
        preset=preset,
        lossless=lossless,
        threads=threads,
        extract_gain_map=extract_gain_map,
        render_hdr=render_hdr,
        hdr_headroom=hdr_headroom,
        strip_metadata=strip_metadata,
        to_srgb=to_srgb,
        intent=intent,
        overwrite=overwrite,
        skip_existing=skip_existing,
    )


def _discover_conversion_tasks(
    sources: List[Path],
    out_dir: Path,
    target_format: Optional[str],
    recursive: bool = False,
    ext_filter: Optional[str] = None,
) -> List[Tuple[Path, Path, str]]:
    tasks: List[Tuple[Path, Path, str]] = []

    valid_exts = {
        ".heic",
        ".heif",
        ".avif",
        ".hif",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".tiff",
        ".tif",
        ".jp2",
    }
    if ext_filter:
        allowed_exts = {
            f".{e.strip().lstrip('.').lower()}"
            for e in ext_filter.split(",")
            if e.strip()
        }
    else:
        allowed_exts = valid_exts

    out_ext = (target_format.lower() if target_format else "jpg").lstrip(".")
    if out_ext == "jpeg":
        out_ext = "jpg"

    for src in sources:
        if not src.exists():
            continue
        if src.is_file():
            if src.suffix.lower() in allowed_exts:
                tgt = out_dir / f"{src.stem}.{out_ext}"
                tasks.append((src, tgt, target_format or "jpeg"))
        elif src.is_dir():
            pattern = "**/*" if recursive else "*"
            for p in sorted(src.glob(pattern)):
                if p.is_file() and p.suffix.lower() in allowed_exts:
                    rel = p.relative_to(src)
                    tgt = (out_dir / rel).with_suffix(f".{out_ext}")
                    tasks.append((p, tgt, target_format or "jpeg"))

    return tasks


def _batch_convert(
    tasks: List[Tuple[Path, Path, str]],
    quality: int,
    preset: str,
    lossless: bool,
    threads: int,
    render_hdr: bool,
    hdr_headroom: Optional[float],
    strip_metadata: bool,
    to_srgb: bool,
    intent: str,
    overwrite: bool,
    skip_existing: bool,
    jobs: int,
    json_output: bool,
) -> None:
    if not tasks:
        typer.echo("Error: No matching image files found to convert.", err=True)
        raise typer.Exit(code=1)

    t_start = time.perf_counter()
    task_args = [
        (
            src,
            tgt,
            fmt,
            quality,
            preset,
            lossless,
            threads,
            None,
            render_hdr,
            hdr_headroom,
            strip_metadata,
            to_srgb,
            intent,
            overwrite,
            skip_existing,
        )
        for src, tgt, fmt in tasks
    ]

    results: List[Dict[str, Any]] = []

    if jobs > 0:
        max_workers = jobs
    else:
        sched_affinity = getattr(os, "sched_getaffinity", None)
        if sched_affinity is not None:
            try:
                max_workers = len(sched_affinity(0))
            except Exception:
                max_workers = os.cpu_count() or 4
        else:
            max_workers = os.cpu_count() or 4
        max_workers = min(max_workers, 16)

    max_workers = min(max_workers, len(tasks))

    if json_output:
        if max_workers <= 1:
            for arg in task_args:
                results.append(_batch_convert_worker(arg))
        else:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=max_workers
            ) as executor:
                for res in executor.map(_batch_convert_worker, task_args):
                    results.append(res)
    else:
        console = Console()
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            main_task = progress.add_task(
                f"Converting {len(tasks)} images", total=len(tasks)
            )
            if max_workers <= 1:
                for arg in task_args:
                    res = _batch_convert_worker(arg)
                    results.append(res)
                    progress.advance(main_task)
            else:
                with concurrent.futures.ProcessPoolExecutor(
                    max_workers=max_workers
                ) as executor:
                    for res in executor.map(_batch_convert_worker, task_args):
                        results.append(res)
                        progress.advance(main_task)

    t_end = time.perf_counter()
    elapsed = max(t_end - t_start, 0.001)

    total = len(tasks)
    succeeded = sum(1 for r in results if r.get("status") == "success")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    failed = sum(1 for r in results if r.get("status") == "failed")
    fps = round(total / elapsed, 1)

    bytes_orig = sum(
        r.get("source_size_bytes", 0) for r in results if r.get("status") == "success"
    )
    bytes_conv = sum(
        r.get("target_size_bytes", 0) for r in results if r.get("status") == "success"
    )

    if json_output:
        manifest = {
            "summary": {
                "total": total,
                "succeeded": succeeded,
                "skipped": skipped,
                "failed": failed,
                "elapsed_seconds": round(elapsed, 3),
                "images_per_second": fps,
                "bytes_original": bytes_orig,
                "bytes_converted": bytes_conv,
                "compression_ratio": round(bytes_conv / bytes_orig, 3)
                if bytes_orig > 0
                else 1.0,
            },
            "results": results,
        }
        print(json.dumps(manifest, indent=2))
    else:
        table = Table(
            title="Batch Conversion Summary",
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Metric", style="bold yellow")
        table.add_column("Value", style="green")

        table.add_row("Total Images", str(total))
        table.add_row("Succeeded", f"[bold green]{succeeded}[/bold green]")
        if skipped:
            table.add_row("Skipped", f"[yellow]{skipped}[/yellow]")
        if failed:
            table.add_row("Failed", f"[bold red]{failed}[/bold red]")
        table.add_row("Total Time", f"{elapsed:.2f}s ({fps} img/s)")

        if bytes_orig > 0:
            saved = bytes_orig - bytes_conv
            ratio = (saved / bytes_orig) * 100
            style_tag = "bold green" if ratio >= 0 else "bold red"
            table.add_row(
                "Storage",
                f"{bytes_orig / (1024 * 1024):.1f} MB -> {bytes_conv / (1024 * 1024):.1f} MB "
                f"([{style_tag}]{'-' if ratio >= 0 else '+'}{abs(ratio):.1f}%[/])",
            )
        console.print(table)

        if failed > 0:
            err_table = Table(
                title="Failed Files", header_style="bold red", border_style="red"
            )
            err_table.add_column("Source", style="yellow")
            err_table.add_column("Error", style="red")
            for r in results:
                if r.get("status") == "failed":
                    err_table.add_row(
                        Path(r["source"]).name, r.get("error", "Unknown error")
                    )
            console.print(err_table)

    if failed > 0 and succeeded == 0:
        raise typer.Exit(code=1)


@app.command(
    "convert",
    help="Convert images between HEIC, AVIF, JPEG, and PNG formats (single file or batch).",
)
def convert_cmd(
    sources: List[Path] = typer.Argument(
        ...,
        help="Source image(s), input directory, or source file followed by target file.",
    ),
    out_dir: Optional[Path] = typer.Option(
        None,
        "--out-dir",
        "-o",
        help="Output directory for converted files (required when converting multiple files or a directory).",
    ),
    format: Optional[str] = typer.Option(
        None,
        "--format",
        "-f",
        help="Target format override: heic, avif, jpeg, png (default: inferred from target extension)",
    ),
    quality: int = typer.Option(
        80,
        "--quality",
        "-q",
        min=1,
        max=100,
        help="Encoding quality (1-100, default: 80)",
    ),
    preset: str = typer.Option(
        "balanced",
        "--preset",
        "-p",
        help="Encoding speed preset: ultrafast, fast, balanced, quality (default: balanced)",
    ),
    lossless: bool = typer.Option(
        False,
        "--lossless",
        help="Enable lossless compression",
    ),
    jobs: int = typer.Option(
        0,
        "--jobs",
        help="Parallel worker processes for batch conversion (0 = auto-detect CPU quota)",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Recursively convert images in subdirectories and mirror directory structure",
    ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        help="Skip files that already exist in the target location",
    ),
    ext: Optional[str] = typer.Option(
        None,
        "--ext",
        help="Comma-separated extensions to include when searching directories (e.g. '.heic,.heif,.avif')",
    ),
    threads: int = typer.Option(
        0,
        "--threads",
        "-t",
        help="Codec threads to use (0 = auto-detect CPU quota)",
    ),
    extract_gain_map: Optional[Path] = typer.Option(
        None,
        "--extract-gain-map",
        help="Extract the auxiliary Gain Map image to a separate file (e.g. gainmap.png)",
    ),
    render_hdr: bool = typer.Option(
        False,
        "--render-hdr",
        help="Render tonemapped HDR appearance using Gain Map before converting",
    ),
    hdr_headroom: Optional[float] = typer.Option(
        None,
        "--hdr-headroom",
        help="Target display HDR headroom factor (e.g. 2.0 or 4.0) for --render-hdr",
    ),
    strip_metadata: bool = typer.Option(
        False,
        "--strip-metadata",
        help="Do not copy EXIF/XMP metadata into destination file",
    ),
    to_srgb: bool = typer.Option(
        False,
        "--to-srgb",
        help="Transform wide-gamut colors (Display P3, BT.2020) to standard sRGB via LittleCMS 2",
    ),
    intent: str = typer.Option(
        "perceptual",
        "--intent",
        help="ICC rendering intent: perceptual, relative, saturation, absolute",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite target if it already exists",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output structured JSON result",
    ),
) -> None:
    """Convert an image between HEIC, AVIF, JPEG, and PNG formats."""
    # 1. If --out-dir is explicitly given
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        tasks = _discover_conversion_tasks(sources, out_dir, format, recursive, ext)
        _batch_convert(
            tasks,
            quality=quality,
            preset=preset,
            lossless=lossless,
            threads=threads,
            render_hdr=render_hdr,
            hdr_headroom=hdr_headroom,
            strip_metadata=strip_metadata,
            to_srgb=to_srgb,
            intent=intent,
            overwrite=overwrite,
            skip_existing=skip_existing,
            jobs=jobs,
            json_output=json_output,
        )
        return

    # 2. If exactly two arguments given: check if second is directory or file
    if len(sources) == 2:
        src, tgt = sources[0], sources[1]
        if src.is_dir() or (tgt.exists() and tgt.is_dir()):
            tgt.mkdir(parents=True, exist_ok=True)
            tasks = _discover_conversion_tasks([src], tgt, format, recursive, ext)
            _batch_convert(
                tasks,
                quality=quality,
                preset=preset,
                lossless=lossless,
                threads=threads,
                render_hdr=render_hdr,
                hdr_headroom=hdr_headroom,
                strip_metadata=strip_metadata,
                to_srgb=to_srgb,
                intent=intent,
                overwrite=overwrite,
                skip_existing=skip_existing,
                jobs=jobs,
                json_output=json_output,
            )
            return
        else:
            # Classic single file mode: `heif convert in.heic out.jpg`
            if not src.exists():
                typer.echo(
                    f"Error: Invalid value for 'SOURCE': Path '{src}' does not exist.",
                    err=True,
                )
                raise typer.Exit(code=2)
            res = _convert_single_file(
                source=src,
                target=tgt,
                format=format,
                quality=quality,
                preset=preset,
                lossless=lossless,
                threads=threads,
                extract_gain_map=extract_gain_map,
                render_hdr=render_hdr,
                hdr_headroom=hdr_headroom,
                strip_metadata=strip_metadata,
                to_srgb=to_srgb,
                intent=intent,
                overwrite=overwrite,
                skip_existing=skip_existing,
            )
            if res["status"] == "failed":
                typer.echo(res["error"], err=True)
                raise typer.Exit(code=res.get("exit_code", 1))
            elif res["status"] == "skipped":
                typer.echo(f"Skipped '{src.name}': {res.get('reason')}")
                return

            if _is_json_mode(json_output):
                print(json.dumps(res, indent=2))
            else:
                target_size = float(str(res["target_size_bytes"]))
                typer.echo(
                    f"Successfully converted '{src.name}' -> '{tgt.name}' "
                    f"({target_size / 1024:.1f} KB, format={res['format']})"
                )
            return

    # 3. If multiple arguments given and the last one is a directory
    if len(sources) > 2 and (sources[-1].is_dir() or not sources[-1].suffix):
        tgt_dir = sources[-1]
        tgt_dir.mkdir(parents=True, exist_ok=True)
        tasks = _discover_conversion_tasks(
            sources[:-1], tgt_dir, format, recursive, ext
        )
        _batch_convert(
            tasks,
            quality=quality,
            preset=preset,
            lossless=lossless,
            threads=threads,
            render_hdr=render_hdr,
            hdr_headroom=hdr_headroom,
            strip_metadata=strip_metadata,
            to_srgb=to_srgb,
            intent=intent,
            overwrite=overwrite,
            skip_existing=skip_existing,
            jobs=jobs,
            json_output=json_output,
        )
        return

    # 4. If single argument given:
    if len(sources) == 1:
        if sources[0].is_dir():
            typer.echo(
                "Error: When source is a directory, please specify --out-dir / -o or target directory.",
                err=True,
            )
            raise typer.Exit(code=2)
        else:
            typer.echo(
                "Error: Please specify target file, target directory, or --out-dir / -o.",
                err=True,
            )
            raise typer.Exit(code=2)

    typer.echo(
        "Error: Converting multiple files requires an output directory (--out-dir / -o or last argument).",
        err=True,
    )
    raise typer.Exit(code=2)


# =====================================================================
# 3. metadata commands
# =====================================================================
@metadata_app.command("dump", help="Dump all metadata blocks present in the image.")
def metadata_dump(
    file: Path = typer.Argument(
        ...,
        help="Path to HEIF/AVIF image file",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output machine-readable JSON format"
    ),
) -> None:
    """Dump all metadata blocks (EXIF, XMP, ICC) found in the image."""
    try:
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(str(file))
        handle = ctx.get_primary_image_handle()
    except Exception:
        if importlib.util.find_spec("PIL") is None:
            typer.echo(
                f"Error: '{file.name}' is not a HEIF/AVIF image. "
                f"Dumping metadata for non-HEIF formats (JPEG, PNG, etc.) requires 'Pillow'.\n"
                f"Please install it via: pip install 'pylibheif[pillow]' or pip install pillow",
                err=True,
            )
            raise typer.Exit(code=1)

        _metadata_dump_pillow(file, json_output)
        return

    blocks: List[Dict[str, Any]] = []
    for mid in handle.get_metadata_block_ids():
        mtype = handle.get_metadata_block_type(mid)
        mdata = handle.get_metadata_block(mid)
        block_entry: Dict[str, Any] = {
            "id": mid,
            "type": mtype,
            "size_bytes": len(mdata),
        }
        if mtype.lower() == "exif":
            parsed_exif = _parse_exif_block(mdata)
            block_entry["parsed_exif"] = parsed_exif
        elif mtype.lower() in ("xmp", "mime") or "xml" in mtype.lower():
            try:
                xmp_text = mdata.decode("utf-8", errors="replace")
                block_entry["content_utf8"] = xmp_text
            except Exception:
                pass
        blocks.append(block_entry)

    out_data = {
        "file": str(file.resolve()),
        "total_blocks": len(blocks),
        "blocks": blocks,
    }

    if _is_json_mode(json_output):
        print(json.dumps(out_data, indent=2, ensure_ascii=False))
        return

    console = Console()
    table = Table(title=f"Metadata Blocks: [bold cyan]{file.name}[/bold cyan]")
    table.add_column("Block ID", justify="right", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Size (Bytes)", justify="right", style="green")

    for b in blocks:
        table.add_row(str(b["id"]), b["type"], str(b["size_bytes"]))

    console.print(table)

    # Directly display full content previews for each block
    for b in blocks:
        mtype = b["type"].lower()
        if mtype == "exif" and b.get("parsed_exif"):
            exif_table = Table(
                title=f"EXIF Tags: [bold cyan]{file.name}[/bold cyan] (Block {b['id']})"
            )
            exif_table.add_column("Tag Name", style="cyan")
            exif_table.add_column("Value", style="green")
            for k, v in sorted(b["parsed_exif"].items()):
                if k != "GPS":
                    exif_table.add_row(str(k), str(v))
            console.print(exif_table)

            if "GPS" in b["parsed_exif"] and isinstance(b["parsed_exif"]["GPS"], dict):
                gps_table = Table(title=f"GPS Information (Block {b['id']})")
                gps_table.add_column("GPS Tag", style="cyan")
                gps_table.add_column("Value", style="green")
                for k, v in sorted(b["parsed_exif"]["GPS"].items()):
                    gps_table.add_row(str(k), str(v))
                console.print(gps_table)

        elif (mtype in ("mime", "xmp") or "xml" in mtype) and b.get("content_utf8"):
            console.print(
                Panel(
                    Syntax(
                        b["content_utf8"].strip(),
                        "xml",
                        theme="monokai",
                        line_numbers=True,
                        word_wrap=True,
                    ),
                    title=f"XMP / MIME Metadata: [bold cyan]{file.name}[/bold cyan] (Block {b['id']})",
                )
            )


@metadata_app.command(
    "extract", help="Extract raw metadata binary (e.g. EXIF or XMP) to a file."
)
def metadata_extract(
    file: Path = typer.Argument(
        ...,
        help="Path to HEIF/AVIF image file",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    out_file: Path = typer.Option(
        ...,
        "--out",
        "-o",
        help="Output destination path for extracted metadata binary",
    ),
    meta_type: str = typer.Option(
        "exif",
        "--type",
        "-t",
        help="Type of metadata to extract: exif, xmp, or specific block id",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite output file if exists",
    ),
) -> None:
    """Extract a raw metadata payload to an external binary file."""
    if out_file.exists() and not overwrite:
        typer.echo(
            f"Error: Output file '{out_file}' already exists. Use -y / --overwrite.",
            err=True,
        )
        raise typer.Exit(code=3)

    try:
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(str(file))
        handle = ctx.get_primary_image_handle()
    except Exception:
        if importlib.util.find_spec("PIL") is None:
            typer.echo(
                f"Error: '{file.name}' is not a HEIF/AVIF image. "
                f"Extracting metadata from non-HEIF formats (JPEG, PNG, etc.) requires 'Pillow'.\n"
                f"Please install it via: pip install 'pylibheif[pillow]' or pip install pillow",
                err=True,
            )
            raise typer.Exit(code=1)

        _metadata_extract_pillow(file, out_file, meta_type)
        return

    block_data: Optional[bytes] = None
    target_type = meta_type.lower()

    for mid in handle.get_metadata_block_ids():
        mtype = handle.get_metadata_block_type(mid).lower()
        if target_type == str(mid) or target_type in mtype:
            block_data = handle.get_metadata_block(mid)
            break

    if block_data is None:
        typer.echo(
            f"Error: No metadata block matching '{meta_type}' was found in '{file.name}'.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        out_file.write_bytes(block_data)
        typer.echo(
            f"Extracted {len(block_data)} bytes ({meta_type}) to '{out_file.name}'"
        )
    except Exception as e:
        typer.echo(f"Failed to write metadata: {e}", err=True)
        raise typer.Exit(code=1)


# =====================================================================
# 4. doctor command
# =====================================================================
@app.command(
    "doctor", help="Inspect runtime environment, codec support, and thread limits."
)
def doctor_cmd(
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output machine-readable JSON format"
    ),
) -> None:
    """Diagnose environment capabilities, installed codecs, and multithreading quotas."""
    encoders = [desc.id_name for desc in pylibheif.get_encoder_descriptors()]

    pillow_installed = False
    pillow_version = None
    try:
        import PIL

        pillow_installed = True
        pillow_version = getattr(PIL, "__version__", "unknown")
    except ImportError:
        pass

    concurrency_info = {
        "hardware_threads": os.cpu_count() or 1,
        "default_codec_threads": pylibheif.get_default_num_threads(),
        "default_encoder_preset": pylibheif.get_default_encoder_preset(),
    }

    supported_formats = {
        "heic_hevc": "x265" in encoders or "kvazaar" in encoders,
        "avif_av1": "aom" in encoders,
        "jpeg": "jpeg" in encoders,
        "jpeg2000": "openjpeg" in encoders,
    }

    doc_data = {
        "pylibheif_version": pylibheif.__version__,
        "libheif_version": pylibheif.get_libheif_version(),
        "encoders": encoders,
        "formats": supported_formats,
        "concurrency": concurrency_info,
        "pillow_integration": {
            "installed": pillow_installed,
            "version": pillow_version,
        },
    }

    if _is_json_mode(json_output):
        print(json.dumps(doc_data, indent=2))
        return

    console = Console()
    console.print(Panel.fit("[bold green]pylibheif System Diagnostics[/bold green]"))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="yellow")
    table.add_column("Status / Value", style="green")

    table.add_row("pylibheif Version", str(doc_data["pylibheif_version"]))
    table.add_row("libheif Version", str(doc_data["libheif_version"]))
    table.add_row("Encoders Available", ", ".join(encoders) or "None")
    table.add_row(
        "Supported Formats",
        f"HEIC: {'✅' if supported_formats['heic_hevc'] else '❌'} | "
        f"AVIF: {'✅' if supported_formats['avif_av1'] else '❌'} | "
        f"JPEG2000: {'✅' if supported_formats['jpeg2000'] else '❌'}",
    )
    table.add_row("Hardware Threads", str(concurrency_info["hardware_threads"]))
    table.add_row(
        "Default Codec Threads", str(concurrency_info["default_codec_threads"])
    )
    table.add_row(
        "Default Encoder Preset", str(concurrency_info["default_encoder_preset"])
    )
    table.add_row(
        "Pillow Integration",
        f"{'Installed (v' + str(pillow_version) + ')' if pillow_installed else 'Not installed'}",
    )

    console.print(table)


def main() -> None:
    """CLI application entrypoint."""
    app()


if __name__ == "__main__":
    main()
