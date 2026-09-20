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
) -> Image.Image:
    """Convert a HeifImage or HeifImageHandle into a Pillow Image.Image.

    Args:
        source: A HeifImageHandle or HeifImage instance.
        convert_hdr_to_8bit: If True, downsamples 10/12/16-bit HDR pixels to 8-bit for
                             universal compatibility with standard Pillow filters.
                             If False, preserves native bit depth when possible.
        options: Optional HeifDecodingOptions for fine-grained decoder control.
        num_threads: Optional override for decoding thread count.

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
    if bit_depth == 8 and im.mode in ("RGB", "RGBA"):
        raw_bytes = im.tobytes()
        heif_image = HeifImage.from_buffer(
            raw_bytes,
            im.width,
            im.height,
            HeifColorspace.RGB,
            chroma,
            bit_depth=8,
        )
    else:
        # High bit-depth or non-standard format
        arr = np.asarray(im)
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
