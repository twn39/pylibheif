"""Conversion utilities between pylibheif (HeifImage / HeifImageHandle) and Pillow (PIL.Image)."""

from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
from PIL import Image

from .._pylibheif import (
    HeifChannel,
    HeifChroma,
    HeifColorspace,
    HeifDecodingOptions,
    HeifImage,
    HeifImageHandle,
)
from .metadata import extract_metadata_to_info


def to_pillow(
    source: Union[HeifImage, HeifImageHandle],
    convert_hdr_to_8bit: bool = True,
    options: Optional[HeifDecodingOptions] = None,
    num_threads: Optional[int] = None,
    target_colorspace: Optional[Union[str, bytes]] = None,
    intent: Union[Any, int, str] = 0,
    bpc: bool = True,
) -> Image.Image:
    """Convert a HeifImage or HeifImageHandle into a Pillow Image.Image.

    Args:
        source: A HeifImageHandle or HeifImage instance.
        convert_hdr_to_8bit: If True, downsamples 10/12/16-bit HDR pixels to 8-bit for
                             universal compatibility with standard Pillow filters.
                             If False, preserves native bit depth when possible.
        options: Optional HeifDecodingOptions for fine-grained decoder control.
        num_threads: Optional override for decoding thread count.
        target_colorspace: Optional target color space name or ICC bytes (e.g. "sRGB", "Display P3").
        intent: Rendering intent for color transformation.
        bpc: Enable black point compensation.

    Returns:
        A PIL.Image.Image instance with EXIF, ICC, XMP and HDR metadata preserved in .info.
    """
    info: Dict[str, Any] = {}

    if isinstance(source, HeifImageHandle):
        handle = source
        info = extract_metadata_to_info(handle)
        has_alpha = getattr(handle, "has_alpha", False)
        chroma = HeifChroma.InterleavedRGBA if has_alpha else HeifChroma.InterleavedRGB
        heif_image = handle.decode(
            HeifColorspace.RGB, chroma, options=options, num_threads=num_threads
        )
        # Check for Gain Map (HDR)
        if getattr(handle, "has_gain_map", False):
            try:
                gm_handle = handle.get_gain_map_handle()
                gm_decoded = gm_handle.decode(HeifColorspace.RGB, HeifChroma.InterleavedRGB)
                gm_plane = gm_decoded.get_plane(HeifChannel.Interleaved, writeable=False)
                gm_arr = np.asarray(gm_plane)
                info["gain_map"] = Image.fromarray(gm_arr)
                if hasattr(handle, "get_gain_map_metadata"):
                    gm_meta = handle.get_gain_map_metadata()
                    if gm_meta is not None:
                        info["gain_map_metadata"] = gm_meta
            except Exception:
                pass
    elif isinstance(source, HeifImage):
        heif_image = source
    else:
        raise TypeError(f"Expected HeifImage or HeifImageHandle, got {type(source)}")

    plane = heif_image.get_plane(HeifChannel.Interleaved, writeable=False)
    arr = np.asarray(plane)

    # Handle high bit-depth (10-bit / 12-bit / 16-bit)
    if arr.dtype == np.uint16 and convert_hdr_to_8bit:
        bit_depth = info.get("bit_depth", 10)
        shift = max(0, bit_depth - 8)
        if shift > 0:
            np.right_shift(arr, shift, out=arr)
        arr = arr.astype(np.uint8, copy=False)

    # Create Pillow Image
    pil_image = Image.fromarray(arr)
    if info:
        pil_image.info.update(info)

    if target_colorspace is not None:
        from ..color import resolve_profile_bytes, transform_colorspace

        src_profile = pil_image.info.get("icc_profile")
        if not src_profile:
            nclx_dict = pil_image.info.get("nclx_profile")
            if nclx_dict:
                from ..color import nclx_to_icc_profile

                class _DummyNclx:
                    pass

                d = _DummyNclx()
                d.color_primaries = nclx_dict.get("color_primaries", 1)
                src_profile = nclx_to_icc_profile(d)

        orig_info = dict(pil_image.info)
        pil_image = transform_colorspace(
            pil_image,
            src_profile=src_profile or "sRGB",
            dst_profile=target_colorspace,
            intent=intent,
            bpc=bpc,
            as_pillow=True,
        )
        pil_image.info.update(orig_info)
        pil_image.info["icc_profile"] = resolve_profile_bytes(target_colorspace)

    return pil_image


def from_pillow(
    pil_image: Image.Image,
    bit_depth: int = 8,
) -> Tuple[HeifImage, Dict[Any, Any]]:
    """Convert a Pillow Image.Image into a pylibheif HeifImage.

    Args:
        pil_image: A PIL.Image.Image instance.
        bit_depth: Target bit depth (8, 10, 12, 16).

    Returns:
        A tuple of (HeifImage, info_dict) where info_dict contains EXIF, ICC, XMP.
    """
    # Normalize mode
    if pil_image.mode in ("RGBA", "LA") or "transparency" in pil_image.info:
        im = pil_image.convert("RGBA")
        chroma = HeifChroma.InterleavedRGBA
    elif pil_image.mode in ("RGB", "L"):
        im = pil_image
        if im.mode == "L":
            im = im.convert("RGB")
        chroma = HeifChroma.InterleavedRGB
    else:
        im = pil_image.convert("RGB")
        chroma = HeifChroma.InterleavedRGB

    # Fast direct buffer path when bit_depth == 8 and mode is standard 8-bit RGB/RGBA
    # Avoid im.tobytes() which allocates and copies memory for the entire image.
    arr = np.asarray(im)
    if bit_depth == 8 and im.mode in ("RGB", "RGBA"):
        heif_image = HeifImage.from_buffer(
            arr,
            im.width,
            im.height,
            HeifColorspace.RGB,
            chroma,
            bit_depth=8,
        )
    else:
        # High bit-depth or non-standard format
        if arr.dtype == np.uint16:
            heif_image = HeifImage.from_numpy(arr, bit_depth=bit_depth)
        else:
            heif_image = HeifImage.from_numpy(arr)

    # Attach ICC profile if present
    icc_profile = pil_image.info.get("icc_profile")
    if icc_profile:
        try:
            heif_image.set_raw_color_profile("prof", icc_profile)
        except Exception:
            pass

    return heif_image, pil_image.info
