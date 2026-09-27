"""Handle extensions, color management, Gain Map helpers, and Pillow bridge."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union

from ._pylibheif import (
    HeifChannel,
    HeifChroma,
    HeifColorspace,
    HeifDecodingOptions,
    HeifEncoder,
    HeifImage,
    HeifImageHandle,
)
from ._proxy import get_encoder_parameters
from .color import (
    SRGB_ICC_BYTES,
    RenderingIntent,
    get_profile_info,
    nclx_to_icc_profile,
    transform_colorspace,
)
from .gain_map import (
    GainMap,
    GainMapMetadata,
    extract_gain_map,
)

# --- Pillow (PIL) Interoperability ---


def to_pillow(
    source: Any,
    convert_hdr_to_8bit: bool = True,
    options: Optional[HeifDecodingOptions] = None,
    num_threads: Optional[int] = None,
) -> Any:
    """Convert a HeifImage or HeifImageHandle into a Pillow Image."""
    try:
        from .pillow.convert import to_pillow as _to_pillow
    except ImportError as e:
        raise ImportError(
            "pylibheif.to_pillow() requires 'Pillow'. "
            "Please install it via: pip install 'pylibheif[pillow]' or pip install pillow"
        ) from e

    return _to_pillow(
        source,
        convert_hdr_to_8bit=convert_hdr_to_8bit,
        options=options,
        num_threads=num_threads,
    )


def from_pillow(pil_image: Any, bit_depth: int = 8) -> Any:
    """Convert a Pillow Image into a pylibheif HeifImage."""
    try:
        from .pillow.convert import from_pillow as _from_pillow
    except ImportError as e:
        raise ImportError(
            "pylibheif.from_pillow() requires 'Pillow'. "
            "Please install it via: pip install 'pylibheif[pillow]' or pip install pillow"
        ) from e

    img, _ = _from_pillow(pil_image, bit_depth=bit_depth)
    return img


def register_pillow_opener() -> None:
    """Register pylibheif as a HEIF/AVIF image opener in Pillow."""
    try:
        from .pillow.plugin import register_heif_opener
    except ImportError as e:
        raise ImportError(
            "pylibheif.register_pillow_opener() requires 'Pillow'. "
            "Please install it via: pip install 'pylibheif[pillow]' or pip install pillow"
        ) from e

    register_heif_opener()


def unregister_pillow_opener() -> None:
    """Unregister pylibheif handler from Pillow."""
    try:
        from .pillow.plugin import unregister_heif_opener
    except ImportError as e:
        raise ImportError(
            "pylibheif.unregister_pillow_opener() requires 'Pillow'. "
            "Please install it via: pip install 'pylibheif[pillow]' or pip install pillow"
        ) from e

    unregister_heif_opener()


# Attach convenience methods to C++ classes


def _handle_get_gain_map(self: HeifImageHandle) -> Optional[GainMap]:
    """Retrieve the primary GainMap domain entity, or None if absent."""
    return extract_gain_map(self)


def _handle_get_gain_map_ids(self: HeifImageHandle) -> List[int]:
    """Find all auxiliary image IDs corresponding to HDR Gain Maps."""
    gain_ids = []
    for aid in self.get_auxiliary_image_ids():
        try:
            aux_handle = self.get_auxiliary_image_handle(aid)
            atype = aux_handle.get_auxiliary_type().lower()
            if "gainmap" in atype or "21496" in atype or "hdrgainmap" in atype:
                gain_ids.append(aid)
        except Exception:
            pass
    return gain_ids


def _handle_has_gain_map(self: HeifImageHandle) -> bool:
    """Return True if image handle has an associated Gain Map."""
    return self.gain_map is not None


def _handle_get_gain_map_handle(self: HeifImageHandle) -> HeifImageHandle:
    """Return auxiliary image handle for the Gain Map."""
    gm = self.gain_map
    if gm is None:
        raise ValueError("Image handle does not contain a Gain Map")
    return gm.aux_handle


def _handle_get_gain_map_metadata(self: HeifImageHandle) -> Optional[GainMapMetadata]:
    """Extract Gain Map metadata from XMP packet attached to gain map or master image."""
    gm = self.gain_map
    return gm.metadata if gm is not None else None


def _handle_decode_gain_map(self: HeifImageHandle) -> Any:
    """Decode primary gain map image and return as a numpy array in range [0, 1]."""
    gm = self.gain_map
    if gm is None:
        raise ValueError("Image handle does not contain a Gain Map")
    return gm.decode()


def _handle_reconstruct_hdr(
    self: HeifImageHandle,
    target_headroom: Optional[float] = None,
    output_format: str = "linear",
    display_boost: Optional[float] = None,
) -> Any:
    """Reconstruct an HDR image from this handle and its embedded Gain Map."""
    gm = self.gain_map
    if gm is None:
        raise ValueError("Image handle does not contain a Gain Map.")
    return gm.reconstruct(
        target_headroom=target_headroom,
        output_format=output_format,
        display_boost=display_boost,
    )


def _handle_decode_depth(self: HeifImageHandle) -> Any:
    """Decode primary depth image and return as a 2D numpy array."""
    depth_handle = self.get_primary_depth_image_handle()
    decoded = depth_handle.decode(HeifColorspace.Monochrome, HeifChroma.Monochrome)
    plane = decoded.get_plane(HeifChannel.Y)
    import numpy as np

    return np.asarray(plane)



# -----------------------------------------------------------------------------
# Color Management Extensions (LittleCMS 2)
# -----------------------------------------------------------------------------

_orig_handle_decode = HeifImageHandle.decode


def _handle_decode(
    self: HeifImageHandle,
    colorspace: HeifColorspace = HeifColorspace.RGB,
    chroma: HeifChroma = HeifChroma.InterleavedRGB,
    options: Optional[HeifDecodingOptions] = None,
    num_threads: Optional[int] = None,
    target_colorspace: Optional[Union[str, bytes]] = None,
    intent: Union[RenderingIntent, int, str] = RenderingIntent.PERCEPTUAL,
    bpc: bool = True,
    prefer_nclx: bool = False,
) -> HeifImage:
    """Decode image handle with optional LittleCMS target color space conversion."""
    if num_threads is not None:
        raw_img = _orig_handle_decode(self, colorspace, chroma, options, num_threads)
    elif options is not None:
        raw_img = _orig_handle_decode(self, colorspace, chroma, options)
    else:
        raw_img = _orig_handle_decode(self, colorspace, chroma)

    if target_colorspace is not None:
        plane = raw_img.get_plane(HeifChannel.Interleaved, writeable=False)
        import numpy as np

        arr = np.asarray(plane)
        src_profile = _handle_get_color_profile_bytes(self, prefer_nclx=prefer_nclx)
        transformed_arr = transform_colorspace(
            arr,
            src_profile=src_profile,
            dst_profile=target_colorspace,
            intent=intent,
            bpc=bpc,
            as_pillow=False,
        )
        return HeifImage.from_numpy(transformed_arr)

    return raw_img




def _handle_get_color_profile_bytes(
    self: HeifImageHandle, prefer_nclx: bool = False
) -> bytes:
    """Retrieve effective ICC profile bytes according to MIAF rules."""
    nclx = None
    try:
        nclx = self.get_nclx_color_profile()
    except Exception:
        pass

    if prefer_nclx and nclx is not None:
        synth = nclx_to_icc_profile(nclx)
        if synth:
            return synth

    # Check raw ICC
    try:
        raw_icc = self.get_raw_color_profile()
        if raw_icc and len(raw_icc) > 0:
            return raw_icc
    except Exception:
        pass

    # Fallback to NCLX synthesis
    if nclx is not None:
        synth = nclx_to_icc_profile(nclx)
        if synth:
            return synth

    return SRGB_ICC_BYTES


def _handle_get_color_profile_info(
    self: HeifImageHandle, prefer_nclx: bool = False
) -> Dict[str, Any]:
    """Return dictionary of color profile metadata and wide gamut detection."""
    p_bytes = _handle_get_color_profile_bytes(self, prefer_nclx=prefer_nclx)
    return get_profile_info(p_bytes)


def _handle_decode_to_srgb(
    self: HeifImageHandle,
    intent: Union[RenderingIntent, int, str] = RenderingIntent.PERCEPTUAL,
    bpc: bool = True,
    as_pillow: bool = False,
    prefer_nclx: bool = False,
) -> Any:
    """Decode image and accurately transform pixels to sRGB color space."""
    chroma = (
        HeifChroma.InterleavedRGBA
        if getattr(self, "has_alpha", False)
        else HeifChroma.InterleavedRGB
    )
    raw_img = _orig_handle_decode(self, HeifColorspace.RGB, chroma)
    plane = raw_img.get_plane(HeifChannel.Interleaved, writeable=False)
    import numpy as np

    arr = np.asarray(plane)
    src_profile = _handle_get_color_profile_bytes(self, prefer_nclx=prefer_nclx)
    return transform_colorspace(
        arr,
        src_profile=src_profile,
        dst_profile="sRGB",
        intent=intent,
        bpc=bpc,
        as_pillow=as_pillow,
    )




def install_handle_extensions() -> None:
    """Attach dynamic convenience properties and methods to C++ classes."""
    HeifEncoder.parameters = property(get_encoder_parameters)
    HeifImageHandle.thumbnails = property(
        lambda self: [self.get_thumbnail(tid) for tid in self.get_thumbnail_ids()]
    )
    setattr(HeifImageHandle, "to_pillow", to_pillow)
    setattr(HeifImage, "to_pillow", to_pillow)
    setattr(HeifImage, "from_pillow", staticmethod(from_pillow))

    setattr(HeifImageHandle, "gain_map", property(_handle_get_gain_map))
    setattr(HeifImageHandle, "gain_map_ids", property(_handle_get_gain_map_ids))
    setattr(HeifImageHandle, "has_gain_map", property(_handle_has_gain_map))
    setattr(HeifImageHandle, "get_gain_map_handle", _handle_get_gain_map_handle)
    setattr(HeifImageHandle, "get_gain_map_image_handle", _handle_get_gain_map_handle)
    setattr(HeifImageHandle, "get_gain_map_metadata", _handle_get_gain_map_metadata)
    setattr(HeifImageHandle, "decode_gain_map", _handle_decode_gain_map)
    setattr(HeifImageHandle, "reconstruct_hdr", _handle_reconstruct_hdr)
    setattr(HeifImageHandle, "decode_depth", _handle_decode_depth)

    setattr(HeifImageHandle, "decode", _handle_decode)
    setattr(HeifImageHandle, "get_color_profile_bytes", _handle_get_color_profile_bytes)
    setattr(HeifImageHandle, "get_color_profile_info", _handle_get_color_profile_info)
    setattr(HeifImageHandle, "decode_to_srgb", _handle_decode_to_srgb)
