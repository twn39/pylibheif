"""Pillow (PIL) integration for pylibheif."""

import importlib.util

if importlib.util.find_spec("PIL") is None:
    raise ImportError(
        "Using the 'pylibheif.pillow' submodule requires the 'Pillow' package. "
        "Please install it via: pip install 'pylibheif[pillow]' or pip install pillow"
    )

from .convert import from_pillow, to_pillow
from .metadata import (
    DISPLAY_P3_ICC_BYTES,
    extract_metadata_to_info,
    normalize_exif_for_pillow,
    pack_exif_for_heif,
)
from .plugin import (
    HeifImageFile,
    register_heif_opener,
    unregister_heif_opener,
)

__all__ = [
    "to_pillow",
    "from_pillow",
    "HeifImageFile",
    "register_heif_opener",
    "unregister_heif_opener",
    "DISPLAY_P3_ICC_BYTES",
    "normalize_exif_for_pillow",
    "pack_exif_for_heif",
    "extract_metadata_to_info",
]
