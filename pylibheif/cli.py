"""Command-line interface for pylibheif (heif / heic / pylibheif).

Designed for both interactive command-line use and deterministic AI agent automation.
Supports structured JSON output (--json), cross-format conversion, metadata inspection,
and environment diagnostics.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
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
            summary["GPS Location"] = f"{lat_val} {lat_ref}, {lon_val} {lon_ref}{alt_suffix}"

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
        xmp_text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    elif "XML:com.adobe.xmp" in im.info:
        raw = im.info["XML:com.adobe.xmp"]
        xmp_text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    has_xmp = bool(xmp_text)

    shooting_summary = _get_shooting_summary(parsed_exif)

    meta_blocks: List[Dict[str, Any]] = []
    if parsed_exif:
        meta_blocks.append({
            "id": 1,
            "type": "Exif",
            "size_bytes": len(im.info.get("exif", b"")),
            "parsed_exif": parsed_exif,
        })
    if xmp_text:
        meta_blocks.append({
            "id": 2,
            "type": "mime",
            "size_bytes": len(xmp_text.encode("utf-8")),
            "content_utf8": xmp_text,
        })
    if has_icc:
        meta_blocks.append({
            "id": 3,
            "type": "icc",
            "size_bytes": len(im.info["icc_profile"]),
        })

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
    table = Table(title=f"Image Information: [bold cyan]{file.name}[/bold cyan] ({fmt})")
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
        xmp_text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    elif "XML:com.adobe.xmp" in im.info:
        raw = im.info["XML:com.adobe.xmp"]
        xmp_text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)

    blocks: List[Dict[str, Any]] = []
    block_id = 1
    if parsed_exif:
        blocks.append({
            "id": block_id,
            "type": "Exif",
            "size_bytes": len(im.info.get("exif", b"")),
            "parsed_exif": parsed_exif,
        })
        block_id += 1
    if xmp_text:
        blocks.append({
            "id": block_id,
            "type": "mime",
            "size_bytes": len(xmp_text.encode("utf-8")),
            "content_utf8": xmp_text,
        })
        block_id += 1
    if "icc_profile" in im.info:
        blocks.append({
            "id": block_id,
            "type": "icc",
            "size_bytes": len(im.info["icc_profile"]),
        })
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
            exif_table = Table(title=f"EXIF Tags: [bold cyan]{file.name}[/bold cyan] (Block {b['id']})")
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
        typer.echo(f"Error: No metadata of type '{meta_type}' found in '{file.name}'.", err=True)
        raise typer.Exit(code=1)

    out_file.write_bytes(raw_data)
    typer.echo(f"Successfully extracted {len(raw_data)} bytes of '{meta_type}' metadata to '{out_file}'.")


# =====================================================================
# 1. info command
# =====================================================================
@app.command("info", help="Inspect image dimensions, color profiles, HDR tags, and metadata.")
def info_cmd(
    file: Path = typer.Argument(
        ...,
        help="Path to HEIF/AVIF/HEIC/JPEG/PNG image file",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output machine-readable JSON format"
    ),
    detail: bool = typer.Option(
        False, "--detail", "-d", help="Include detailed ICC/NCLX and metadata blocks"
    ),
) -> None:
    """Inspect image dimensions, channels, bit depth, color profile, and HDR metadata."""
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
                    "red_primary": mdcv.red_primary,
                    "green_primary": mdcv.green_primary,
                    "blue_primary": mdcv.blue_primary,
                    "white_point": mdcv.white_point,
                    "max_luminance": mdcv.max_luminance,
                    "min_luminance": mdcv.min_luminance,
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

    # Rich human-readable display
    console = Console()
    table = Table(title=f"Image Information: [bold cyan]{file.name}[/bold cyan]")
    table.add_column("Property", style="bold yellow")
    table.add_column("Value", style="green")

    table.add_row("Resolution", f"{handle.width} x {handle.height}")
    table.add_row("Bit Depth", f"{handle.luma_bits_per_pixel}-bit (chroma: {handle.chroma_bits_per_pixel}-bit)")
    table.add_row("Alpha Channel", "Yes" if handle.has_alpha else "No")
    table.add_row("File Size", f"{data['size_bytes'] / 1024:.1f} KB ({data['size_bytes']} bytes)")
    table.add_row("Images in File", f"{len(image_ids)} (primary id: {primary_id})")
    table.add_row("Thumbnails", str(handle.number_of_thumbnails))
    table.add_row("Depth Map", "Yes" if handle.has_depth_image else "No")
    if handle.has_gain_map:
        if gm_meta_dict:
            fmt = gm_meta_dict.get("format_type", "Gain Map")
            headroom = gm_meta_dict.get("hdr_capacity_max", 0.0)
            boost = gm_meta_dict.get("max_content_boost", 1.0)
            gamma_val = gm_meta_dict.get("gamma", [1.0])[0]
            table.add_row(
                "Gain Map (HDR)",
                f"Yes ({fmt}, Max: {boost:.2f}x / {headroom:.2f} EV, Gamma: {gamma_val:.2f})",
            )
        else:
            table.add_row("Gain Map (HDR)", "Yes")
    else:
        table.add_row("Gain Map (HDR)", "No")

    prof_str = color_profile_type
    if color_info and color_info.get("name") and color_info["name"] != "Unknown":
        prof_str += f" ({color_info['name']})"
    if color_info.get("is_wide_gamut"):
        prof_str += " [bold magenta](Wide Gamut)[/bold magenta]"
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
        "Metadata",
        f"EXIF: {'Yes' if has_exif else 'No'} | XMP: {'Yes' if has_xmp else 'No'} | Blocks: {len(meta_blocks)}",
    )
    if hdr_info:
        hdr_desc = []
        if "clli" in hdr_info:
            hdr_desc.append(f"CLLI (Max: {hdr_info['clli']['max_content_light_level']} nits)")
        if "mdcv" in hdr_info:
            hdr_desc.append(f"MDCV (Max: {hdr_info['mdcv']['max_luminance']} nits)")
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


# =====================================================================
# 2. convert command
# =====================================================================
@app.command("convert", help="Convert images between HEIC, AVIF, JPEG, and PNG formats.")
def convert_cmd(
    source: Path = typer.Argument(
        ...,
        help="Source image path",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    target: Path = typer.Argument(
        ...,
        help="Target output image path",
        dir_okay=False,
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
    if target.exists() and not overwrite:
        typer.echo(
            f"Error: Target file '{target}' already exists. Use --overwrite / -y to replace.",
            err=True,
        )
        raise typer.Exit(code=3)

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
        typer.echo(
            f"Error: Unsupported target format '{fmt_str}'. Expected: heic, avif, jpeg, png.",
            err=True,
        )
        raise typer.Exit(code=2)

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
                        typer.echo(f"Extracted auxiliary Gain Map to '{extract_gain_map}'.")
                    except Exception as e:
                        typer.echo(f"Warning: Failed to extract gain map: {e}", err=True)
                else:
                    typer.echo(f"Warning: '{source.name}' does not contain an auxiliary Gain Map.", err=True)

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
                    # Reconstruct HDR into sRGB uint8 HeifImage
                    hdr_arr = handle.reconstruct_hdr(display_boost=hdr_headroom, output_format="srgb_uint8")
                    raw_img = pylibheif.HeifImage.from_buffer(
                        hdr_arr,
                        hdr_arr.shape[1],
                        hdr_arr.shape[0],
                        pylibheif.HeifColorspace.RGB,
                        pylibheif.HeifChroma.InterleavedRGB,
                    )
                else:
                    # Decode handle to HeifImage
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

                # Encode primary image
                out_handle = encoder.encode_image(out_ctx, raw_img, preset=preset)

                # If source has gain map, not rendering HDR, and metadata not stripped -> preserve gain map
                if handle.has_gain_map and not render_hdr and not strip_metadata:
                    try:
                        gm_img = handle.decode_gain_map()
                        aux_encoder = pylibheif.HeifEncoder(comp_fmt, preset=preset)
                        aux_handle = aux_encoder.encode_image(out_ctx, gm_img, preset=preset)
                        gm_meta = handle.get_gain_map_metadata()
                        urn = "urn:iso:std:iso:ts:21496-1"
                        if gm_meta and gm_meta.format_type == "Apple":
                            urn = "urn:com:apple:photo:2020:aux:hdrgainmap"
                        out_ctx.assign_auxiliary_image(out_handle, aux_handle, urn)
                    except Exception:
                        pass

                # Metadata forwarding
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
                # Target is PNG or JPEG -> via Pillow
                try:
                    from PIL import Image
                    from pylibheif.pillow import to_pillow
                except ImportError:
                    typer.echo(
                        "Error: Converting to PNG/JPEG requires 'Pillow'. "
                        "Install via: pip install 'pylibheif[pillow]'",
                        err=True,
                    )
                    raise typer.Exit(code=2)

                if render_hdr and handle.has_gain_map:
                    hdr_arr = handle.reconstruct_hdr(display_boost=hdr_headroom, output_format="srgb_uint8")
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
                typer.echo(
                    "Error: Converting from PNG/JPEG requires 'Pillow'. "
                    "Install via: pip install 'pylibheif[pillow]'",
                    err=True,
                )
                raise typer.Exit(code=2)

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

                    heif_img, pil_info = from_pillow(pil_img)
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
        typer.echo(f"Conversion failed: {e}", err=True)
        raise typer.Exit(code=1)

    result_data = {
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
    }

    if _is_json_mode(json_output):
        print(json.dumps(result_data, indent=2))
    else:
        target_size = float(str(result_data["target_size_bytes"]))
        typer.echo(
            f"Successfully converted '{source.name}' -> '{target.name}' "
            f"({target_size / 1024:.1f} KB, format={target_fmt})"
        )


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
            exif_table = Table(title=f"EXIF Tags: [bold cyan]{file.name}[/bold cyan] (Block {b['id']})")
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


@metadata_app.command("extract", help="Extract raw metadata binary (e.g. EXIF or XMP) to a file.")
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
        typer.echo(f"Error: Output file '{out_file}' already exists. Use -y / --overwrite.", err=True)
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
        typer.echo(f"Error: No metadata block matching '{meta_type}' was found in '{file.name}'.", err=True)
        raise typer.Exit(code=1)

    try:
        out_file.write_bytes(block_data)
        typer.echo(f"Extracted {len(block_data)} bytes ({meta_type}) to '{out_file.name}'")
    except Exception as e:
        typer.echo(f"Failed to write metadata: {e}", err=True)
        raise typer.Exit(code=1)


# =====================================================================
# 4. doctor command
# =====================================================================
@app.command("doctor", help="Inspect runtime environment, codec support, and thread limits.")
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
    table.add_row("Default Codec Threads", str(concurrency_info["default_codec_threads"]))
    table.add_row("Default Encoder Preset", str(concurrency_info["default_encoder_preset"]))
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
