"""Command-line interface for pylibheif (heif / heic / pylibheif).

Designed for both interactive command-line use and deterministic AI agent automation.
Supports structured JSON output (--json), cross-format conversion, metadata inspection,
and environment diagnostics.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import typer
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    print(
        "Error: 'typer' and 'rich' are required for the CLI. "
        "Install them via: pip install 'pylibheif[cli]'",
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


# =====================================================================
# 1. info command
# =====================================================================
@app.command("info", help="Inspect image dimensions, color profiles, HDR tags, and metadata.")
def info_cmd(
    file: Path = typer.Argument(
        ...,
        help="Path to HEIF/AVIF/HEIC image file",
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
    except Exception as e:
        typer.echo(f"Error opening image '{file}': {e}", err=True)
        raise typer.Exit(code=1)

    image_ids = ctx.get_list_of_top_level_image_IDs()
    primary_id = image_ids[0] if image_ids else 0

    # Collect metadata blocks
    meta_blocks: List[Dict[str, Any]] = []
    has_exif = False
    has_xmp = False
    for mid in handle.get_metadata_block_ids():
        mtype = handle.get_metadata_block_type(mid)
        mdata = handle.get_metadata_block(mid)
        if mtype.lower() == "exif":
            has_exif = True
        elif mtype.lower() == "mime" or "xml" in mtype.lower() or "xmp" in mtype.lower():
            has_xmp = True
        meta_blocks.append({"id": mid, "type": mtype, "size_bytes": len(mdata)})

    # Color profile
    color_profile_type = str(handle.color_profile_type).split(".")[-1]
    has_icc = color_profile_type == "Prof"
    has_nclx = color_profile_type == "Nclx"
    nclx_details: Optional[Dict[str, Any]] = None
    if has_nclx:
        nclx = handle.get_nclx_color_profile()
        if nclx:
            nclx_details = {
                "color_primaries": int(nclx.color_primaries),
                "transfer_characteristics": int(nclx.transfer_characteristics),
                "matrix_coefficients": int(nclx.matrix_coefficients),
                "full_range_flag": bool(nclx.full_range_flag),
            }

    # HDR Metadata
    hdr_info: Dict[str, Any] = {}
    if getattr(handle, "has_content_light_level", False):
        try:
            clli = getattr(handle, "content_light_level", None)
            if clli is None and hasattr(handle, "get_content_light_level"):
                clli = handle.get_content_light_level()
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
            if mdcv is None and hasattr(handle, "get_mastering_display_colour_volume"):
                mdcv = handle.get_mastering_display_colour_volume()
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
            if amve is None and hasattr(handle, "get_ambient_viewing_environment"):
                amve = handle.get_ambient_viewing_environment()
            if amve:
                hdr_info["amve"] = {
                    "ambient_illumination": amve.ambient_illumination,
                    "ambient_light": amve.ambient_light,
                }
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
        "color_profile": {
            "type": color_profile_type,
            "has_icc": has_icc,
            "has_nclx": has_nclx,
            **({"nclx": nclx_details} if (detail and nclx_details) else {}),
        },
        "metadata_summary": {
            "has_exif": has_exif,
            "has_xmp": has_xmp,
            "total_blocks": len(meta_blocks),
        },
        "hdr": hdr_info or None,
    }

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
    table.add_row("Gain Map (HDR)", "Yes" if handle.has_gain_map else "No")
    table.add_row("Color Profile", color_profile_type)
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
    strip_metadata: bool = typer.Option(
        False,
        "--strip-metadata",
        help="Do not copy EXIF/XMP metadata into destination file",
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
                # Decode handle to HeifImage
                decode_opts = pylibheif.HeifDecodingOptions()
                if threads > 0:
                    decode_opts.num_codec_threads = threads
                raw_img = handle.decode(
                    pylibheif.HeifColorspace.RGB,
                    pylibheif.HeifChroma.InterleavedRGB,
                    options=decode_opts,
                )

                # Encode
                encoder.encode_image(out_ctx, raw_img, preset=preset)

                # Metadata forwarding
                if not strip_metadata:
                    for mid in handle.get_metadata_block_ids():
                        mtype = handle.get_metadata_block_type(mid)
                        mdata = handle.get_metadata_block(mid)
                        # Add to primary image if possible
                        try:
                            out_handle = out_ctx.get_primary_image_handle()
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

                pil_img = to_pillow(handle)
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
                    save_kwargs = {}
                    if target_fmt == "jpeg":
                        save_kwargs["quality"] = quality
                        if pil_img.mode in ("RGBA", "P"):
                            pil_img = pil_img.convert("RGB")
                    pil_img.save(str(target), **save_kwargs)

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
        "target_size_bytes": os.path.getsize(target),
    }

    if _is_json_mode(json_output):
        print(json.dumps(result_data, indent=2))
    else:
        typer.echo(
            f"Successfully converted '{source.name}' -> '{target.name}' "
            f"({result_data['target_size_bytes'] / 1024:.1f} KB, format={target_fmt})"
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
    except Exception as e:
        typer.echo(f"Error reading file '{file}': {e}", err=True)
        raise typer.Exit(code=1)

    blocks: List[Dict[str, Any]] = []
    for mid in handle.get_metadata_block_ids():
        mtype = handle.get_metadata_block_type(mid)
        mdata = handle.get_metadata_block(mid)
        block_entry: Dict[str, Any] = {
            "id": mid,
            "type": mtype,
            "size_bytes": len(mdata),
        }
        # If text-based (XMP), attempt utf-8 decode preview
        if mtype.lower() in ("xmp", "mime") or "xml" in mtype.lower():
            try:
                block_entry["preview_utf8"] = mdata[:500].decode("utf-8", errors="replace")
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
    except Exception as e:
        typer.echo(f"Error reading file '{file}': {e}", err=True)
        raise typer.Exit(code=1)

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

    table.add_row("pylibheif Version", doc_data["pylibheif_version"])
    table.add_row("libheif Version", doc_data["libheif_version"])
    table.add_row("Encoders Available", ", ".join(encoders) or "None")
    table.add_row(
        "Supported Formats",
        f"HEIC: {'✅' if supported_formats['heic_hevc'] else '❌'} | "
        f"AVIF: {'✅' if supported_formats['avif_av1'] else '❌'} | "
        f"JPEG2000: {'✅' if supported_formats['jpeg2000'] else '❌'}",
    )
    table.add_row("Hardware Threads", str(concurrency_info["hardware_threads"]))
    table.add_row("Default Codec Threads", str(concurrency_info["default_codec_threads"]))
    table.add_row("Default Encoder Preset", concurrency_info["default_encoder_preset"])
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
