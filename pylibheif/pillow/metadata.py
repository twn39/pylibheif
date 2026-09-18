"""Metadata utilities for synchronizing EXIF, ICC, XMP and HDR metadata with Pillow."""

import base64
from typing import Any, Dict, Optional, Tuple

# Standard minimal Apple Display P3 ICC profile (536 bytes)
# Used when NCLX color_primaries == 12 (Display P3) and no embedded ICC profile is present
DISPLAY_P3_ICC_BYTES = base64.b64decode(
    b"AAACGGFwcGwEAAAAbW50clJHQiBYWVogB+YAAQABAAAAAAAAYWNzcEFQUEwAAAAAQVBQTAAAAAAA"
    b"AAAAAAAAAAAAAAAAAPbWAAEAAAAA0y1hcHBsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    b"AAAAAAAAAAAAAAAAAAAAAAAKZGVzYwAAAPwAAAAwY3BydAAAASwAAABQd3RwdAAAAXwAAAAUclhZ"
    b"WgAAAZAAAAAUZ1hZWgAAAaQAAAAUYlhZWgAAAbgAAAAUclRSQwAAAcwAAAAgY2hhZAAAAewAAAAs"
    b"YlRSQwAAAcwAAAAgZ1RSQwAAAcwAAAAgbWx1YwAAAAAAAAABAAAADGVuVVMAAAAUAAAAHABEAGkA"
    b"cwBwAGwAYQB5ACAAUAAzbWx1YwAAAAAAAAABAAAADGVuVVMAAAA0AAAAHABDAG8AcAB5AHIAaQBn"
    b"AGgAdAAgAEEAcABwAGwAZQAgAEkAbgBjAC4ALAAgADIAMAAyADJYWVogAAAAAAAA9tUAAQAAAAAA"
    b"0y1hcHBsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKZGVz"
    b"YwAAAPwAAAAwY3BydAAAASwAAABQd3RwdAAAAXwAAAAUclhZWgAAAZAAAAAUZ1hZWgAAAaQAAAAU"
    b"YlhZWgAAAbgAAAAUclRSQwAAAcwAAAAgY2hhZAAAAewAAAAsYlRSQwAAAcwAAAAgZ1RSQwAAAcwA"
    b"AAAg"
)

# Standard valid Display P3 binary from Apple ColorSync
_APPLE_P3_B64 = (
    b"AAACGGFwcGwEAAAAbW50clJHQiBYWVogB+YAAQABAAAAAAAAYWNzcEFQUEwAAAAAQVBQTAAAAAAA"
    b"AAAAAAAAAAAAAAAAAPbWAAEAAAAA0y1hcHBsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    b"AAAAAAAAAAAAAAAAAAAAAAAKZGVzYwAAAPwAAAAwY3BydAAAASwAAABQd3RwdAAAAXwAAAAUclhZ"
    b"WgAAAZAAAAAUZ1hZWgAAAaQAAAAUYlhZWgAAAbgAAAAUclRSQwAAAcwAAAAgY2hhZAAAAewAAAAs"
    b"YlRSQwAAAcwAAAAgZ1RSQwAAAcwAAAAgbWx1YwAAAAAAAAABAAAADGVuVVMAAAAUAAAAHABEAGkA"
    b"cwBwAGwAYQB5ACAAUAAzbWx1YwAAAAAAAAABAAAADGVuVVMAAAA0AAAAHABDAG8AcAB5AHIAaQBn"
    b"AGgAdAAgAEEAcABwAGwAZQAgAEkAbgBjAC4ALAAgADIAMAAyADJYWVogAAAAAAAA9tUAAQAAAAAA"
    b"0y1YWVogAAAAAAAAkdAAAD6tAAAXbFhZWiAAAAAAAACD3wAAPb////+7WFlaIAAAAAAAAEq/AACx"
    b"NwAACrlYWVogAAAAAAAAKDgAABELAADIuXBhcmEAAAAAAAMAAAACZmYAAPKnAAANWQAAE9AAAApb"
    b"c2YzMgAAAAAAAQxCAAAF3v//8yYAAAeTAAD9kP//+6L///2jAAAD3AAAwG4="
)
DISPLAY_P3_ICC_BYTES = base64.b64decode(_APPLE_P3_B64)


def normalize_exif_for_pillow(raw_block: bytes) -> Tuple[Optional[bytes], Optional[int]]:
    """Normalize raw HEIF EXIF block for Pillow.

    Strips the 4-byte big-endian offset prefix added by libheif.
    Resets the EXIF Orientation tag to 1 (Normal) to avoid double-rotation when
    ImageOps.exif_transpose() is used, and returns (normalized_bytes, original_orientation).
    """
    if len(raw_block) < 4:
        return None, None

    # HEIF spec: first 4 bytes is uint32 offset to TIFF header
    payload = raw_block[4:]

    # Ensure TIFF header or Exif header exists
    if not payload.startswith(b"Exif\x00\x00") and (
        payload.startswith(b"II*\x00") or payload.startswith(b"MM\x00*")
    ):
        payload = b"Exif\x00\x00" + payload

    orig_orientation = None
    try:
        from PIL import Image

        temp_img = Image.new("RGB", (1, 1))
        temp_img.info["exif"] = payload
        exif = temp_img.getexif()
        orig_orientation = exif.get(0x0112)  # Tag 274: Orientation
        if orig_orientation is not None and orig_orientation != 1:
            exif[0x0112] = 1
            payload = exif.tobytes()
    except Exception:
        pass

    return payload, orig_orientation


def pack_exif_for_heif(exif_bytes: bytes) -> bytes:
    """Prepare EXIF bytes for libheif's add_exif_metadata.

    libheif's heif_context_add_exif_metadata automatically scans for the TIFF
    header ('MM\\0*' or 'II*\\0') and prepends the 4-byte offset.
    If the caller passed raw bytes that already have a 4-byte prefix before 'Exif' or 'II'/'MM',
    we strip that redundant 4-byte prefix so libheif doesn't double-prepend.
    """
    if len(exif_bytes) > 8:
        # Check if first 4 bytes look like a redundant offset followed by Exif or TIFF
        sub = exif_bytes[4:]
        if sub.startswith(b"Exif\x00\x00") or sub.startswith(b"II*\x00") or sub.startswith(b"MM\x00*"):
            return sub
    return exif_bytes


def extract_metadata_to_info(handle: Any) -> Dict[str, Any]:
    """Extract all metadata from a HeifImageHandle into a Pillow-compatible info dictionary."""
    info: Dict[str, Any] = {}

    # 1. EXIF Metadata
    try:
        exif_ids = handle.get_metadata_block_ids("Exif")
        if exif_ids:
            raw_block = handle.get_metadata_block(exif_ids[0])
            norm_exif, orig_orient = normalize_exif_for_pillow(raw_block)
            if norm_exif:
                info["exif"] = norm_exif
            if orig_orient:
                info["original_orientation"] = orig_orient
    except Exception:
        pass

    # 2. XMP Metadata
    try:
        all_ids = handle.get_metadata_block_ids()
        for mid in all_ids:
            mtype = handle.get_metadata_block_type(mid)
            if mtype in ("mime", "XMP"):
                info["xmp"] = handle.get_metadata_block(mid)
                break
    except Exception:
        pass

    # 3. Color Profile (ICC / NCLX)
    try:
        from .._pylibheif import HeifColorProfileType

        c_type = handle.color_profile_type
        if c_type in (HeifColorProfileType.Prof, HeifColorProfileType.RICC):
            raw_icc = handle.get_raw_color_profile()
            if raw_icc:
                info["icc_profile"] = raw_icc
        elif c_type == HeifColorProfileType.Nclx:
            nclx = handle.get_nclx_color_profile()
            if nclx:
                primaries_val = getattr(nclx.color_primaries, "value", nclx.color_primaries)
                transfer_val = getattr(nclx.transfer_characteristics, "value", nclx.transfer_characteristics)
                matrix_val = getattr(nclx.matrix_coefficients, "value", nclx.matrix_coefficients)
                info["nclx_profile"] = {
                    "color_primaries": primaries_val,
                    "transfer_characteristics": transfer_val,
                    "matrix_coefficients": matrix_val,
                    "full_range_flag": bool(nclx.full_range_flag),
                }
                # Fallback / synthesis for Display P3 (SMPTE_EG_432_1 == 12)
                if primaries_val == 12 and "icc_profile" not in info:
                    info["icc_profile"] = DISPLAY_P3_ICC_BYTES
    except Exception:
        pass

    # 4. HDR Metadata (CLLI / MDCV / AMVE)
    try:
        if getattr(handle, "has_content_light_level", False):
            clli = handle.content_light_level
            if clli:
                info["hdr_clli"] = {
                    "max_content_light_level": clli.max_content_light_level,
                    "max_pic_average_light_level": clli.max_pic_average_light_level,
                }
        if getattr(handle, "has_mastering_display_colour_volume", False):
            mdcv = handle.mastering_display_colour_volume
            if mdcv:
                info["hdr_mdcv"] = {
                    "display_primaries_x": mdcv.display_primaries_x,
                    "display_primaries_y": mdcv.display_primaries_y,
                    "white_point_x": mdcv.white_point_x,
                    "white_point_y": mdcv.white_point_y,
                    "max_display_mastering_luminance": mdcv.max_display_mastering_luminance,
                    "min_display_mastering_luminance": mdcv.min_display_mastering_luminance,
                }
    except Exception:
        pass

    # 5. Bit Depth
    try:
        info["bit_depth"] = handle.luma_bits_per_pixel
    except Exception:
        pass

    return info
