"""Pillow ImagePlugin implementation for HEIF/AVIF image formats."""

import os
from typing import IO, Union, cast
import numpy as np
from PIL import Image, ImageFile

from .._pylibheif import (
    HeifChannel,
    HeifChroma,
    HeifColorspace,
    HeifCompressionFormat,
    HeifContext,
    HeifEncoder,
)
from .convert import from_pillow
from .metadata import extract_metadata_to_info, pack_exif_for_heif


class HeifImageFile(ImageFile.ImageFile):
    """Pillow ImageFile plugin for HEIF/AVIF images powered by pylibheif."""

    format = "HEIF"
    format_description = "HEIF / AVIF image (powered by pylibheif)"

    def __init__(
        self,
        fp: Union[str, bytes, os.PathLike, IO[bytes], None] = None,
        filename: Union[str, bytes, None] = None,
    ):
        self._ctx: Union[HeifContext, None] = None
        self._handle = None
        self._top_level_ids = []
        self._frame_idx = 0
        self._n_frames = 1
        super().__init__(fp if fp is not None else "", filename)

    def _open(self) -> None:
        ctx = HeifContext()

        if isinstance(self.fp, (str, bytes, os.PathLike)):
            ctx.read_from_file(str(os.fspath(self.fp)))
        elif hasattr(self.fp, "read") and hasattr(self.fp, "seek"):
            try:
                self.fp.seek(0)
            except Exception:
                pass
            ctx.read_from_stream(self.fp)
        elif hasattr(self.fp, "read"):
            data = self.fp.read()
            ctx.read_from_memory(data)
        else:
            raise ValueError(f"Unsupported fp type: {type(self.fp)}")

        self._ctx = ctx
        self._top_level_ids = ctx.get_list_of_top_level_image_IDs()
        if not self._top_level_ids:
            raise SyntaxError("No top-level images found in HEIF container")

        self._n_frames = len(self._top_level_ids)
        self.is_animated = self._n_frames > 1
        self._frame_idx = 0

        self._init_frame(0)
        self.tile = []

    def _init_frame(self, frame_idx: int) -> None:
        """Initialize frame metadata and handle without decoding pixel data (lazy)."""
        if self._ctx is not None:
            handle = self._ctx.get_image_handle(self._top_level_ids[frame_idx])
            self._handle = handle
            self._size = (handle.width, handle.height)
            self._mode = "RGBA" if getattr(handle, "has_alpha", False) else "RGB"
            self.info.clear()
            self.info.update(extract_metadata_to_info(handle))

    def load(self):
        """Perform on-demand / lazy decoding of the image frame."""
        if self._handle is not None:
            chroma = (
                HeifChroma.InterleavedRGBA
                if self._mode == "RGBA"
                else HeifChroma.InterleavedRGB
            )
            heif_image = self._handle.decode(HeifColorspace.RGB, chroma)
            plane = heif_image.get_plane(HeifChannel.Interleaved, writeable=False)
            arr = np.asarray(plane)

            if arr.dtype == np.uint16:
                bit_depth = self.info.get("bit_depth", 10)
                shift = max(0, bit_depth - 8)
                arr = (arr >> shift).astype(np.uint8)

            im = Image.fromarray(arr)
            self.im = im.im

            # If single-frame, context and handle can be released
            if not self.is_animated:
                self._handle = None
                self._ctx = None

        return super().load()

    def seek(self, frame: int) -> None:
        """Seek to a specific frame within the HEIF image sequence."""
        if frame < 0 or frame >= self._n_frames:
            raise EOFError("attempt to seek outside sequence")
        if frame == self._frame_idx:
            return

        self._frame_idx = frame
        self._init_frame(frame)

        # Reset core image object so next load() produces the new frame
        if hasattr(Image, "core") and hasattr(Image.core, "new"):
            self.im = Image.core.new(self._mode, self._size)

    def tell(self) -> int:
        """Return the current frame index."""
        return self._frame_idx

    @property
    def n_frames(self) -> int:
        """Return the total number of frames."""
        return self._n_frames


def _accept(prefix: bytes) -> bool:
    """Accept function for Pillow Image.register_open."""
    if len(prefix) < 12:
        return False
    if prefix[4:8] != b"ftyp":
        return False
    brand = prefix[8:12]
    return brand in (
        b"heic",
        b"heix",
        b"heim",
        b"heis",
        b"hevc",
        b"hevx",
        b"hevm",
        b"hevs",
        b"mif1",
        b"msf1",
        b"avif",
        b"avis",
    )


def _save(im: Image.Image, fp: Union[IO[bytes], str], filename: Union[str, bytes] = "") -> None:
    """Save function for Pillow Image.register_save."""
    # Determine format: HEVC or AV1
    format_name = getattr(im, "format", "HEIF") or "HEIF"
    ext = os.path.splitext(str(filename))[1].lower() if filename else ""
    if ext in (".avif", ".avis") or format_name.upper() in ("AVIF", "AV1"):
        compression = HeifCompressionFormat.AV1
    else:
        compression = HeifCompressionFormat.HEVC

    # Extract save options
    encoderinfo = getattr(im, "encoderinfo", {})
    quality = encoderinfo.get("quality", 80)
    lossless = encoderinfo.get("lossless", False)

    heif_image, info = from_pillow(im)

    ctx = HeifContext()
    encoder = HeifEncoder(compression)
    if lossless:
        encoder.set_lossless(True)
    else:
        encoder.set_lossy_quality(quality)

    handle = encoder.encode_image(ctx, heif_image)

    # Attach EXIF
    exif = encoderinfo.get("exif") or info.get("exif") or im.info.get("exif")
    if exif:
        if hasattr(exif, "tobytes"):
            exif_bytes = exif.tobytes()
        else:
            exif_bytes = bytes(exif)
        packed_exif = pack_exif_for_heif(exif_bytes)
        try:
            ctx.add_exif_metadata(handle, packed_exif)
        except Exception:
            pass

    # Attach XMP
    xmp = encoderinfo.get("xmp") or info.get("xmp") or im.info.get("xmp")
    if xmp:
        try:
            ctx.add_xmp_metadata(handle, bytes(xmp))
        except Exception:
            pass

    if hasattr(fp, "write"):
        ctx.write_to_stream(fp)
    elif isinstance(fp, (str, bytes, os.PathLike)):
        ctx.write_to_file(str(os.fspath(fp)))
    else:
        with open(str(fp), "wb") as f:
            ctx.write_to_stream(f)


def register_heif_opener() -> None:
    """Register pylibheif as the handler for HEIF / AVIF images in Pillow."""
    Image.register_open(HeifImageFile.format, HeifImageFile, _accept)
    Image.register_save(HeifImageFile.format, _save)
    Image.register_extensions(
        HeifImageFile.format,
        [".heic", ".heif", ".hif", ".heics", ".heifs", ".avif", ".avis"],
    )
    Image.register_mime(HeifImageFile.format, "image/heic")
    Image.register_mime(HeifImageFile.format, "image/heif")
    Image.register_mime(HeifImageFile.format, "image/avif")


def unregister_heif_opener() -> None:
    """Unregister pylibheif handler from Pillow."""
    for ext in (".heic", ".heif", ".hif", ".heics", ".heifs", ".avif", ".avis"):
        if ext in Image.EXTENSION and Image.EXTENSION[ext] == HeifImageFile.format:
            del Image.EXTENSION[ext]
    if HeifImageFile.format in Image.ID:
        Image.ID.remove(HeifImageFile.format)
    if HeifImageFile.format in Image.SAVE:
        del Image.SAVE[HeifImageFile.format]
    if HeifImageFile.format in Image.MIME:
        del Image.MIME[HeifImageFile.format]
