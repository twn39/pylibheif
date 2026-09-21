"""Pillow ImagePlugin implementation for HEIF/AVIF image formats."""

import os
from typing import IO, Union, Optional, List, Any, Dict
import numpy as np
from PIL import Image, ImageFile

from .._pylibheif import (
    HeifChannel,
    HeifChroma,
    HeifColorspace,
    HeifCompressionFormat,
    HeifContext,
    HeifEncoder,
    HeifImageHandle,
    HeifTrackType,
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
        self._handle: Optional[HeifImageHandle] = None
        self._top_level_ids: List[int] = []
        self._is_sequence_track: bool = False
        self._frames: List[Any] = []
        self._durations: List[int] = []
        self._frame_idx = 0
        self._n_frames = 1
        super().__init__(fp if fp is not None else "", filename)

    def _open(self) -> None:
        ctx = HeifContext()

        if self.fp is None:
            raise ValueError("fp cannot be None")
        elif isinstance(self.fp, (str, bytes, os.PathLike)):
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
        self._is_sequence_track = False
        self._frames = []
        self._durations = []

        if ctx.has_sequence():
            self._is_sequence_track = True
            track = ctx.get_track(0)
            self._track = track
            self.is_animated = True
            timescale = track.timescale or 1000

            while True:
                img = track.decode_next_image()
                if img is None:
                    break
                self._frames.append(img)
                ms = (
                    int(round((img.duration * 1000.0) / timescale))
                    if timescale > 0
                    else 100
                )
                self._durations.append(ms)

            if not self._frames:
                raise SyntaxError("Empty sequence track in HEIF container")

            self._n_frames = len(self._frames)
            self._frame_idx = 0
            w, h = track.resolution
            self._size = (w, h)
            self._mode = "RGBA" if track.has_alpha_channel else "RGB"
            reps = track.number_of_repetitions
            loop_val = 0 if (reps == 0 or reps == 0xFFFFFFFF) else reps
            self.info["loop"] = loop_val
            self.info["duration"] = self._durations[0] if self._durations else 100
            self._init_track_frame(0)
            self.tile = []
            return

        self._top_level_ids = ctx.get_list_of_top_level_image_IDs()
        if not self._top_level_ids:
            raise SyntaxError("No top-level images found in HEIF container")

        self._n_frames = len(self._top_level_ids)
        self.is_animated = self._n_frames > 1
        self._frame_idx = 0

        self._init_frame(0)
        self.tile = []

    def _init_track_frame(self, frame_idx: int) -> None:
        """Initialize frame size and duration for sequence track."""
        if 0 <= frame_idx < len(self._frames):
            heif_image = self._frames[frame_idx]
            self._size = (heif_image.width, heif_image.height)
            self.info["duration"] = self._durations[frame_idx]

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
        if self._is_sequence_track:
            if 0 <= self._frame_idx < len(self._frames):
                heif_image = self._frames[self._frame_idx]
                plane = heif_image.get_plane(HeifChannel.Interleaved, writeable=False)
                arr = np.asarray(plane)

                if arr.dtype == np.uint16:
                    bit_depth = self.info.get("bit_depth", 10)
                    shift = max(0, bit_depth - 8)
                    if shift > 0:
                        np.right_shift(arr, shift, out=arr)
                    arr = arr.astype(np.uint8, copy=False)

                im = Image.fromarray(arr)
                self.im = im.im
            return super().load()

        if self._handle is not None:
            chroma = (
                HeifChroma.InterleavedRGBA
                if self._mode == "RGBA"
                else HeifChroma.InterleavedRGB
            )
            opts = self.info.get("decoding_options", None)
            num_threads = self.info.get("num_threads", None)
            heif_image = self._handle.decode(
                HeifColorspace.RGB, chroma, options=opts, num_threads=num_threads
            )
            plane = heif_image.get_plane(HeifChannel.Interleaved, writeable=False)
            arr = np.asarray(plane)

            if arr.dtype == np.uint16:
                bit_depth = self.info.get("bit_depth", 10)
                shift = max(0, bit_depth - 8)
                if shift > 0:
                    np.right_shift(arr, shift, out=arr)
                arr = arr.astype(np.uint8, copy=False)

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
        if self._is_sequence_track:
            self._init_track_frame(frame)
        else:
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

    @property
    def has_gain_map(self) -> bool:
        """Return True if image contains an auxiliary HDR Gain Map."""
        return self.get_gain_map() is not None

    def get_gain_map(self) -> Optional[Image.Image]:
        """Decode and return the embedded Gain Map as a PIL Image."""
        if "gain_map" in self.info and isinstance(self.info["gain_map"], Image.Image):
            return self.info["gain_map"]
        if self._handle is not None and getattr(self._handle, "has_gain_map", False):
            gm_handle = self._handle.get_gain_map_handle()
            gm_decoded = gm_handle.decode(HeifColorspace.RGB, HeifChroma.InterleavedRGB)
            plane = gm_decoded.get_plane(HeifChannel.Interleaved, writeable=False)
            arr = np.asarray(plane)
            gm_im = Image.fromarray(arr)
            self.info["gain_map"] = gm_im
            return gm_im
        return None

    def render_hdr(
        self,
        target_headroom: Optional[float] = None,
        output_format: str = "srgb_clip",
        display_boost: Optional[float] = None,
        as_pillow: bool = True,
    ) -> Union[Image.Image, np.ndarray]:
        """Reconstruct an HDR image using this base image and embedded Gain Map.

        Args:
            target_headroom: Headroom multiplier (e.g. 2.0 or 4.0). None for full capability.
            output_format: 'linear' (float32/float16), 'pq' (10-bit uint16), or 'srgb_clip'.
            display_boost: Alias for target_headroom.
            as_pillow: If True and output_format is 'srgb_clip', returns a PIL Image.

        Returns:
            PIL Image or Numpy array containing the reconstructed HDR image.
        """
        from ..gain_map import reconstruct_hdr

        self.load()
        gm = self.get_gain_map()
        if gm is None:
            raise ValueError("Image does not contain an HDR Gain Map.")
        meta = self.info.get("gain_map_metadata")
        headroom = target_headroom if target_headroom is not None else display_boost
        arr = reconstruct_hdr(
            self,
            gm,
            metadata=meta,
            target_headroom=headroom,
            output_format=output_format,
            display_boost=display_boost,
        )
        if as_pillow and output_format.lower() in ("srgb_clip", "srgb", "srgb_uint8"):
            return Image.fromarray(arr)
        return arr

    def convert_colorspace(
        self,
        target_profile: Union[str, bytes] = "sRGB",
        intent: Union[Any, int, str] = 0,
        bpc: bool = True,
    ) -> Image.Image:
        """Convert this image's colors to target color space (default: sRGB).

        Preserves Alpha channel, handles wide-gamut Display P3/BT.2020 accurately,
        and returns a newly transformed PIL Image.
        """
        self.load()
        src_profile = self.info.get("icc_profile")
        if not src_profile:
            nclx_dict = self.info.get("nclx_profile")
            if nclx_dict:
                from ..color import nclx_to_icc_profile

                class _DummyNclx:
                    pass

                d = _DummyNclx()
                d.color_primaries = nclx_dict.get("color_primaries", 1)
                src_profile = nclx_to_icc_profile(d)

        from ..color import resolve_profile_bytes, transform_colorspace

        transformed = transform_colorspace(
            self,
            src_profile=src_profile or "sRGB",
            dst_profile=target_profile,
            intent=intent,
            bpc=bpc,
            as_pillow=True,
        )
        transformed.info.update(self.info)
        transformed.info["icc_profile"] = resolve_profile_bytes(target_profile)
        return transformed

    def close(self) -> None:
        self._frames.clear()
        self._durations.clear()
        self._handle = None
        self._ctx = None
        super().close()


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


def _save(
    im: Image.Image,
    fp: Union[IO[bytes], str],
    filename: Union[str, bytes] = "",
    save_format: Optional[str] = None,
) -> None:
    """Save function for Pillow Image.register_save."""
    # Determine format: HEVC or AV1
    format_name = save_format or getattr(im, "format", None) or "HEIF"
    ext = os.path.splitext(str(filename))[1].lower() if filename else ""
    if ext in (".avif", ".avis") or str(format_name).upper() in (
        "AVIF",
        "AVIS",
        "AV1",
    ):
        compression = HeifCompressionFormat.AV1
    else:
        compression = HeifCompressionFormat.HEVC

    # Extract save options
    encoderinfo = getattr(im, "encoderinfo", {})
    quality = encoderinfo.get("quality", 80)
    lossless = encoderinfo.get("lossless", False)
    if quality == -1:
        lossless = True

    preset = encoderinfo.get("preset", "")
    speed = encoderinfo.get("speed", None)
    threads = encoderinfo.get("threads", None)
    tune = encoderinfo.get("tune", None)
    chroma = encoderinfo.get("chroma", None)
    enc_params = encoderinfo.get("enc_params", None)

    save_all = bool(encoderinfo.get("save_all", False))
    append_images = encoderinfo.get("append_images", [])

    if append_images:
        all_frames = [im] + list(append_images)
    elif (save_all or getattr(im, "is_animated", False)) and getattr(im, "n_frames", 1) > 1:
        all_frames = []
        curr = im.tell()
        for i in range(im.n_frames):
            im.seek(i)
            all_frames.append(im.copy())
        im.seek(curr)
    else:
        all_frames = [im]

    if len(all_frames) > 1:
        dur = encoderinfo.get("duration", im.info.get("duration", 100))
        if isinstance(dur, (list, tuple)):
            durations = list(dur)
            while len(durations) < len(all_frames):
                durations.append(durations[-1] if durations else 100)
        else:
            durations = [int(dur)] * len(all_frames)

        loop = int(encoderinfo.get("loop", im.info.get("loop", 0)))

        ctx = HeifContext()
        major_brand = "avis" if compression == HeifCompressionFormat.AV1 else "msf1"
        ctx.set_major_brand(major_brand)
        ctx.add_compatible_brand(major_brand)
        ctx.add_compatible_brand("mif1")
        if compression == HeifCompressionFormat.AV1:
            ctx.add_compatible_brand("avif")
        else:
            ctx.add_compatible_brand("heic")

        timescale = 1000
        ctx.set_sequence_timescale(timescale)
        ctx.set_number_of_sequence_repetitions(loop)

        w, h = im.size
        track = ctx.add_visual_sequence_track(
            w, h, HeifTrackType.ImageSequence, timescale
        )

        encoder = HeifEncoder(compression, preset=str(preset) if preset else "")
        if lossless:
            encoder.set_lossless(True)
        else:
            encoder.set_lossy_quality(int(quality))

        if speed is not None and encoder.has_parameter("speed"):
            encoder.set_integer_parameter("speed", int(speed))
        if threads is not None and encoder.has_parameter("threads"):
            encoder.set_integer_parameter("threads", int(threads))
        if tune is not None and encoder.has_parameter("tune"):
            encoder.set_string_parameter("tune", str(tune))
        if chroma is not None and encoder.has_parameter("chroma"):
            encoder.set_string_parameter("chroma", str(chroma))
        if enc_params and isinstance(enc_params, dict):
            for k, v in enc_params.items():
                encoder.set_parameter(str(k), str(v))

        for idx, frame in enumerate(all_frames):
            frame_img, _ = from_pillow(frame)
            frame_duration_ms = max(1, int(durations[idx]))
            frame_img.duration = frame_duration_ms
            save_alpha = frame.mode in ("RGBA", "LA", "PA")
            track.encode_sequence_image(frame_img, encoder, save_alpha=save_alpha)

        track.encode_end_of_sequence(encoder)

        if hasattr(fp, "write"):
            ctx.write_to_stream(fp)
        elif isinstance(fp, (str, bytes, os.PathLike)):
            ctx.write_to_file(str(os.fspath(fp)))
        else:
            with open(str(fp), "wb") as f:
                ctx.write_to_stream(f)
        return

    heif_image, info = from_pillow(im)

    ctx = HeifContext()
    encoder = HeifEncoder(compression, preset=str(preset) if preset else "")
    if lossless:
        encoder.set_lossless(True)
    else:
        encoder.set_lossy_quality(int(quality))

    # Apply specific parameters if provided
    if speed is not None and encoder.has_parameter("speed"):
        encoder.set_integer_parameter("speed", int(speed))
    if threads is not None and encoder.has_parameter("threads"):
        encoder.set_integer_parameter("threads", int(threads))
    if tune is not None and encoder.has_parameter("tune"):
        encoder.set_string_parameter("tune", str(tune))
    if chroma is not None and encoder.has_parameter("chroma"):
        encoder.set_string_parameter("chroma", str(chroma))

    # Apply arbitrary extra encoder parameters dictionary
    if enc_params and isinstance(enc_params, dict):
        for k, v in enc_params.items():
            encoder.set_parameter(str(k), str(v))

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

    # Attach Gain Map (HDR)
    gain_map_input = encoderinfo.get("gain_map") or im.info.get("gain_map")
    if gain_map_input is not None:
        from ..gain_map import (
            GainMapMetadata,
            generate_gain_map_xmp,
            URN_GAIN_MAP_ISO_21496_1,
        )

        if isinstance(gain_map_input, Image.Image):
            gm_heif, _ = from_pillow(gain_map_input)
        elif isinstance(gain_map_input, np.ndarray):
            gm_heif = HeifImage.from_numpy(gain_map_input)
        elif isinstance(gain_map_input, HeifImage):
            gm_heif = gain_map_input
        else:
            raise TypeError(f"Unsupported gain_map type: {type(gain_map_input)}")

        gm_quality = encoderinfo.get("gain_map_quality", quality)
        gm_encoder = HeifEncoder(compression, preset=str(preset) if preset else "")
        if lossless:
            gm_encoder.set_lossless(True)
        else:
            gm_encoder.set_lossy_quality(int(gm_quality))

        gm_handle = gm_encoder.encode_image(ctx, gm_heif)
        aux_urn = encoderinfo.get("gain_map_urn") or URN_GAIN_MAP_ISO_21496_1
        ctx.assign_auxiliary_image(handle, gm_handle, str(aux_urn))

        gm_meta = encoderinfo.get("gain_map_metadata") or im.info.get("gain_map_metadata")
        if gm_meta is not None:
            if isinstance(gm_meta, dict):
                gm_meta = GainMapMetadata(**gm_meta)
            xmp_bytes = generate_gain_map_xmp(gm_meta)
            try:
                ctx.add_xmp_metadata(gm_handle, xmp_bytes)
            except Exception:
                pass

    if hasattr(fp, "write"):
        ctx.write_to_stream(fp)
    elif isinstance(fp, (str, bytes, os.PathLike)):
        ctx.write_to_file(str(os.fspath(fp)))
    else:
        with open(str(fp), "wb") as f:
            ctx.write_to_stream(f)


def _save_heif(
    im: Image.Image,
    fp: Union[IO[bytes], str],
    filename: Union[str, bytes] = "",
) -> None:
    _save(im, fp, filename, save_format="HEIF")


def _save_avif(
    im: Image.Image,
    fp: Union[IO[bytes], str],
    filename: Union[str, bytes] = "",
) -> None:
    _save(im, fp, filename, save_format="AVIF")


def _save_heic(
    im: Image.Image,
    fp: Union[IO[bytes], str],
    filename: Union[str, bytes] = "",
) -> None:
    _save(im, fp, filename, save_format="HEIC")


def _save_avis(
    im: Image.Image,
    fp: Union[IO[bytes], str],
    filename: Union[str, bytes] = "",
) -> None:
    _save(im, fp, filename, save_format="AVIS")


def _save_heifs(
    im: Image.Image,
    fp: Union[IO[bytes], str],
    filename: Union[str, bytes] = "",
) -> None:
    _save(im, fp, filename, save_format="HEIFS")


def register_heif_opener() -> None:
    """Register pylibheif as the handler for HEIF / AVIF images in Pillow."""
    Image.register_open(HeifImageFile.format, HeifImageFile, _accept)
    handlers = {
        HeifImageFile.format: _save_heif,
        "AVIF": _save_avif,
        "HEIC": _save_heic,
        "HEIFS": _save_heifs,
        "AVIS": _save_avis,
    }
    for fmt, handler in handlers.items():
        Image.register_save(fmt, handler)
        if hasattr(Image, "register_save_all"):
            Image.register_save_all(fmt, handler)
        elif hasattr(Image, "SAVE_ALL"):
            Image.SAVE_ALL[fmt] = handler

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
    for fmt in (HeifImageFile.format, "AVIF", "HEIC", "HEIFS", "AVIS"):
        if fmt in Image.SAVE:
            del Image.SAVE[fmt]
        if hasattr(Image, "SAVE_ALL") and fmt in Image.SAVE_ALL:
            del Image.SAVE_ALL[fmt]
    if HeifImageFile.format in Image.MIME:
        del Image.MIME[HeifImageFile.format]
