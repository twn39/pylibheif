"""Asynchronous wrappers (AsyncHeifContext, AsyncHeifImageHandle, AsyncHeifEncoder, AsyncHeifTrack)."""

from __future__ import annotations
import concurrent.futures
from typing import Any, Dict, List, Literal, Optional, Union, overload

from ._concurrency import _run_in_executor
from ._pylibheif import (
    HeifAmbientViewingEnvironment,
    HeifChroma,
    HeifColorProfileNclx,
    HeifColorProfileType,
    HeifColorspace,
    HeifContentLightLevel,
    HeifContext,
    HeifDecodingOptions,
    HeifDepthRepresentationInfo,
    HeifEncoder,
    HeifEncodingOptions,
    HeifImage,
    HeifImageHandle,
    HeifImageTiling,
    HeifMasteringDisplayColourVolume,
    HeifTrack,
    HeifTrackType,
)
from .color import RenderingIntent
from .gain_map import AsyncGainMap, GainMapMetadata, extract_async_gain_map

class AsyncHeifImageHandle:
    """Async wrapper for HeifImageHandle."""

    def __init__(
        self,
        handle: HeifImageHandle,
        executor: Optional[concurrent.futures.Executor] = None,
    ):
        self._handle = handle
        self._executor = executor

    def __repr__(self) -> str:
        return repr(self._handle).replace("HeifImageHandle", "AsyncHeifImageHandle")

    @property
    def width(self) -> int:
        return self._handle.width

    @property
    def height(self) -> int:
        return self._handle.height

    @property
    def has_alpha(self) -> bool:
        return self._handle.has_alpha

    @property
    def luma_bits_per_pixel(self) -> int:
        return self._handle.luma_bits_per_pixel

    @property
    def chroma_bits_per_pixel(self) -> int:
        return self._handle.chroma_bits_per_pixel

    @property
    def has_content_light_level(self) -> bool:
        return self._handle.has_content_light_level

    @property
    def has_mastering_display_colour_volume(self) -> bool:
        return self._handle.has_mastering_display_colour_volume

    @property
    def has_ambient_viewing_environment(self) -> bool:
        return self._handle.has_ambient_viewing_environment

    @property
    def content_light_level(self) -> Optional[HeifContentLightLevel]:
        return self._handle.content_light_level

    @property
    def mastering_display_colour_volume(
        self,
    ) -> Optional[HeifMasteringDisplayColourVolume]:
        return self._handle.mastering_display_colour_volume

    @property
    def ambient_viewing_environment(self) -> Optional[HeifAmbientViewingEnvironment]:
        return self._handle.ambient_viewing_environment

    @property
    def color_profile_type(self) -> HeifColorProfileType:
        return self._handle.color_profile_type

    def get_raw_color_profile(self) -> bytes:
        return self._handle.get_raw_color_profile()

    async def get_raw_color_profile_async(self) -> bytes:
        return await _run_in_executor(
            self._executor, self._handle.get_raw_color_profile
        )

    def get_nclx_color_profile(self) -> Optional[HeifColorProfileNclx]:
        return self._handle.get_nclx_color_profile()

    async def decode(
        self,
        colorspace: HeifColorspace = HeifColorspace.RGB,
        chroma: HeifChroma = HeifChroma.InterleavedRGB,
        options: Optional[HeifDecodingOptions] = None,
        num_threads: Optional[int] = None,
        target_colorspace: Optional[Union[str, bytes]] = None,
        intent: Union[RenderingIntent, int, str] = RenderingIntent.PERCEPTUAL,
        bpc: bool = True,
        prefer_nclx: bool = False,
    ) -> HeifImage:
        """Asynchronously decode the image with optional color space conversion."""
        return await _run_in_executor(
            self._executor,
            self._handle.decode,
            colorspace,
            chroma,
            options,
            num_threads,
            target_colorspace,
            intent,
            bpc,
            prefer_nclx,
        )

    def get_metadata_block_ids(self, type_filter: str = "") -> List[int]:
        return self._handle.get_metadata_block_ids(type_filter)

    def get_metadata_block_type(self, id: int) -> str:
        return self._handle.get_metadata_block_type(id)

    def get_metadata_block(self, id: int) -> bytes:
        return self._handle.get_metadata_block(id)

    async def get_metadata_block_async(self, id: int) -> bytes:
        return await _run_in_executor(
            self._executor, self._handle.get_metadata_block, id
        )

    def get_auxiliary_image_ids(self, aux_key_mask: int = 0) -> List[int]:
        return self._handle.get_auxiliary_image_ids(aux_key_mask)

    def get_auxiliary_type(self) -> str:
        return self._handle.get_auxiliary_type()

    def get_auxiliary_image_handle(self, id: int) -> "AsyncHeifImageHandle":
        handle = self._handle.get_auxiliary_image_handle(id)
        return AsyncHeifImageHandle(handle, executor=self._executor)

    async def get_auxiliary_image_handle_async(self, id: int) -> "AsyncHeifImageHandle":
        handle = await _run_in_executor(
            self._executor, self._handle.get_auxiliary_image_handle, id
        )
        return AsyncHeifImageHandle(handle, executor=self._executor)

    @property
    def number_of_thumbnails(self) -> int:
        return self._handle.number_of_thumbnails

    def get_number_of_thumbnails(self) -> int:
        return self._handle.get_number_of_thumbnails()

    def get_thumbnail_ids(self) -> List[int]:
        return self._handle.get_thumbnail_ids()

    def get_thumbnail(self, id: int) -> "AsyncHeifImageHandle":
        thumb = self._handle.get_thumbnail(id)
        return AsyncHeifImageHandle(thumb, executor=self._executor)

    async def get_thumbnail_async(self, id: int) -> "AsyncHeifImageHandle":
        thumb = await _run_in_executor(self._executor, self._handle.get_thumbnail, id)
        return AsyncHeifImageHandle(thumb, executor=self._executor)

    async def get_thumbnails(self) -> List["AsyncHeifImageHandle"]:
        ids = self.get_thumbnail_ids()
        return [self.get_thumbnail(tid) for tid in ids]

    def get_image_tiling(self, process_transformations: bool = True) -> HeifImageTiling:
        return self._handle.get_image_tiling(process_transformations)

    async def decode_tile(
        self,
        tile_x: int,
        tile_y: int,
        colorspace: HeifColorspace = HeifColorspace.RGB,
        chroma: HeifChroma = HeifChroma.InterleavedRGB,
        options: Optional[HeifDecodingOptions] = None,
        num_threads: Optional[int] = None,
    ) -> HeifImage:
        return await _run_in_executor(
            self._executor,
            self._handle.decode_tile,
            tile_x,
            tile_y,
            colorspace,
            chroma,
            options,
            num_threads,
        )

    @property
    def has_depth_image(self) -> bool:
        return self._handle.has_depth_image

    def get_number_of_depth_images(self) -> int:
        return self._handle.get_number_of_depth_images()

    def get_depth_image_ids(self) -> List[int]:
        return self._handle.get_depth_image_ids()

    def get_depth_image_handle(self, id: int) -> "AsyncHeifImageHandle":
        handle = self._handle.get_depth_image_handle(id)
        return AsyncHeifImageHandle(handle, executor=self._executor)

    async def get_depth_image_handle_async(self, id: int) -> "AsyncHeifImageHandle":
        handle = await _run_in_executor(
            self._executor, self._handle.get_depth_image_handle, id
        )
        return AsyncHeifImageHandle(handle, executor=self._executor)

    def get_primary_depth_image_handle(self) -> "AsyncHeifImageHandle":
        handle = self._handle.get_primary_depth_image_handle()
        return AsyncHeifImageHandle(handle, executor=self._executor)

    def get_depth_representation_info(
        self, id: int = 0
    ) -> Optional[HeifDepthRepresentationInfo]:
        return self._handle.get_depth_representation_info(id)

    @property
    def gain_map(self) -> Optional[AsyncGainMap]:
        """Asynchronous GainMap domain entity, or None if no gain map exists."""
        return extract_async_gain_map(self)

    @property
    def has_gain_map(self) -> bool:
        return self.gain_map is not None

    def get_gain_map_handle(self) -> "AsyncHeifImageHandle":
        gm = self.gain_map
        if gm is None:
            raise ValueError("Image handle does not contain a Gain Map")
        return gm.aux_handle

    async def get_gain_map_handle_async(self) -> "AsyncHeifImageHandle":
        return self.get_gain_map_handle()

    def get_gain_map_metadata(self) -> Optional[GainMapMetadata]:
        gm = self.gain_map
        return gm.metadata if gm is not None else None

    async def get_gain_map_metadata_async(self) -> Optional[GainMapMetadata]:
        gm = self.gain_map
        if gm is None:
            return None
        return await gm.get_metadata_async()

    def decode_gain_map(self) -> Any:
        gm = self.gain_map
        if gm is None:
            raise ValueError("Image handle does not contain a Gain Map")
        return gm.decode()

    async def decode_gain_map_async(self) -> Any:
        gm = self.gain_map
        if gm is None:
            raise ValueError("Image handle does not contain a Gain Map")
        return await gm.decode_async()

    def reconstruct_hdr(
        self,
        target_headroom: Optional[float] = None,
        output_format: str = "linear",
        display_boost: Optional[float] = None,
    ) -> Any:
        gm = self.gain_map
        if gm is None:
            raise ValueError("Image handle does not contain a Gain Map")
        return gm.reconstruct(
            target_headroom=target_headroom,
            output_format=output_format,
            display_boost=display_boost,
        )

    async def reconstruct_hdr_async(
        self,
        target_headroom: Optional[float] = None,
        output_format: str = "linear",
        display_boost: Optional[float] = None,
    ) -> Any:
        gm = self.gain_map
        if gm is None:
            raise ValueError("Image handle does not contain a Gain Map")
        return await gm.reconstruct_async(
            target_headroom=target_headroom,
            output_format=output_format,
            display_boost=display_boost,
        )

    async def decode_depth(self) -> Any:
        return await _run_in_executor(self._executor, self._handle.decode_depth)

    def get_color_profile_bytes(self, prefer_nclx: bool = False) -> bytes:
        return self._handle.get_color_profile_bytes(prefer_nclx=prefer_nclx)

    async def get_color_profile_bytes_async(self, prefer_nclx: bool = False) -> bytes:
        return await _run_in_executor(
            self._executor, self._handle.get_color_profile_bytes, prefer_nclx
        )

    def get_color_profile_info(self, prefer_nclx: bool = False) -> Dict[str, Any]:
        return self._handle.get_color_profile_info(prefer_nclx=prefer_nclx)

    async def get_color_profile_info_async(
        self, prefer_nclx: bool = False
    ) -> Dict[str, Any]:
        return await _run_in_executor(
            self._executor, self._handle.get_color_profile_info, prefer_nclx
        )

    async def decode_to_srgb(
        self,
        intent: Union[RenderingIntent, int, str] = RenderingIntent.PERCEPTUAL,
        bpc: bool = True,
        as_pillow: bool = False,
        prefer_nclx: bool = False,
    ) -> Any:
        return await _run_in_executor(
            self._executor,
            self._handle.decode_to_srgb,
            intent,
            bpc,
            as_pillow,
            prefer_nclx,
        )


class AsyncHeifContext:
    """Async wrapper for HeifContext with custom executor and async factory support."""

    def __init__(
        self,
        ctx: Optional[HeifContext] = None,
        executor: Optional[concurrent.futures.Executor] = None,
    ):
        self._ctx = ctx or HeifContext()
        self._executor = executor

    @classmethod
    async def from_file(
        cls,
        filename: str,
        executor: Optional[concurrent.futures.Executor] = None,
    ) -> "AsyncHeifContext":
        """Async factory method to construct and read context from file."""
        c = cls(executor=executor)
        await c.read_from_file(filename)
        return c

    @classmethod
    async def from_memory(
        cls,
        data: Union[bytes, bytearray, memoryview],
        executor: Optional[concurrent.futures.Executor] = None,
    ) -> "AsyncHeifContext":
        """Async factory method to construct and read context from memory bytes."""
        c = cls(executor=executor)
        await c.read_from_memory(data)
        return c

    @classmethod
    async def from_stream(
        cls,
        stream: Any,
        executor: Optional[concurrent.futures.Executor] = None,
    ) -> "AsyncHeifContext":
        """Async factory method to construct and read context from a Python stream."""
        c = cls(executor=executor)
        await c.read_from_stream(stream)
        return c

    def __repr__(self) -> str:
        return repr(self._ctx).replace("HeifContext", "AsyncHeifContext")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the context and release resources."""
        self._ctx.close()

    async def reset(self) -> None:
        """Reset context and release buffer references."""
        await _run_in_executor(self._executor, self._ctx.reset)

    @property
    def max_decoding_threads(self) -> int:
        """Maximum background threads used for parallel tile decoding."""
        return self._ctx.max_decoding_threads

    @max_decoding_threads.setter
    def max_decoding_threads(self, value: int) -> None:
        self._ctx.max_decoding_threads = value

    async def set_max_decoding_threads(self, max_threads: int) -> None:
        """Asynchronously set maximum background threads for parallel tile decoding."""
        await _run_in_executor(
            self._executor, self._ctx.set_max_decoding_threads, max_threads
        )

    async def get_max_decoding_threads(self) -> int:
        """Asynchronously get maximum background threads used for parallel tile decoding."""
        return await _run_in_executor(
            self._executor, self._ctx.get_max_decoding_threads
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def read_from_file(self, filename: str) -> None:
        """Asynchronously read from file."""
        await _run_in_executor(self._executor, self._ctx.read_from_file, filename)

    async def read_from_memory(self, data: Union[bytes, bytearray, memoryview]) -> None:
        """Asynchronously read from memory."""
        await _run_in_executor(self._executor, self._ctx.read_from_memory, data)

    async def read_from_stream(self, stream: Any) -> None:
        """Asynchronously read from a Python file-like stream object."""
        await _run_in_executor(self._executor, self._ctx.read_from_stream, stream)

    async def write_to_file(self, filename: str) -> None:
        """Asynchronously write to file."""
        await _run_in_executor(self._executor, self._ctx.write_to_file, filename)

    @overload
    async def write_to_bytes(self, copy: Literal[True] = ...) -> bytes: ...
    @overload
    async def write_to_bytes(self, copy: Literal[False]) -> memoryview: ...
    @overload
    async def write_to_bytes(self, copy: bool = ...) -> Union[bytes, memoryview]: ...
    async def write_to_bytes(self, copy: bool = True) -> Union[bytes, memoryview]:
        """Asynchronously export context to Python bytes (copy=True) or zero-copy memoryview (copy=False)."""
        return await _run_in_executor(self._executor, self._ctx.write_to_bytes, copy)

    async def write_to_memoryview(self) -> memoryview:
        """Asynchronously export context directly to a zero-copy Python memoryview."""
        return await _run_in_executor(self._executor, self._ctx.write_to_memoryview)

    async def write_to_stream(self, stream: Any) -> None:
        """Asynchronously write to a Python file-like stream object."""
        await _run_in_executor(self._executor, self._ctx.write_to_stream, stream)

    def get_primary_image_handle(self) -> AsyncHeifImageHandle:
        """Get async wrapper for primary image handle."""
        handle = self._ctx.get_primary_image_handle()
        return AsyncHeifImageHandle(handle, executor=self._executor)

    async def get_primary_image_handle_async(self) -> AsyncHeifImageHandle:
        """Asynchronously get primary image handle."""
        return await _run_in_executor(self._executor, self.get_primary_image_handle)

    def get_image_handle(self, id: int) -> AsyncHeifImageHandle:
        """Get async wrapper for specific image ID."""
        handle = self._ctx.get_image_handle(id)
        return AsyncHeifImageHandle(handle, executor=self._executor)

    async def get_image_handle_async(self, id: int) -> AsyncHeifImageHandle:
        """Asynchronously get image handle for specific image ID."""
        return await _run_in_executor(self._executor, self.get_image_handle, id)

    def get_list_of_top_level_image_IDs(self) -> List[int]:
        return self._ctx.get_list_of_top_level_image_IDs()

    def add_exif_metadata(
        self, handle: Union[HeifImageHandle, AsyncHeifImageHandle], data: bytes
    ) -> None:
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        self._ctx.add_exif_metadata(h, data)

    async def add_exif_metadata_async(
        self, handle: Union[HeifImageHandle, AsyncHeifImageHandle], data: bytes
    ) -> None:
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        await _run_in_executor(self._executor, self._ctx.add_exif_metadata, h, data)

    def add_xmp_metadata(
        self, handle: Union[HeifImageHandle, AsyncHeifImageHandle], data: bytes
    ) -> None:
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        self._ctx.add_xmp_metadata(h, data)

    async def add_xmp_metadata_async(
        self, handle: Union[HeifImageHandle, AsyncHeifImageHandle], data: bytes
    ) -> None:
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        await _run_in_executor(self._executor, self._ctx.add_xmp_metadata, h, data)

    def add_generic_metadata(
        self,
        handle: Union[HeifImageHandle, AsyncHeifImageHandle],
        data: bytes,
        item_type: str,
        content_type: str = "",
    ) -> None:
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        self._ctx.add_generic_metadata(h, data, item_type, content_type)

    async def add_generic_metadata_async(
        self,
        handle: Union[HeifImageHandle, AsyncHeifImageHandle],
        data: bytes,
        item_type: str,
        content_type: str = "",
    ) -> None:
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        await _run_in_executor(
            self._executor,
            self._ctx.add_generic_metadata,
            h,
            data,
            item_type,
            content_type,
        )

    def assign_thumbnail(
        self,
        master_image: Union[HeifImageHandle, AsyncHeifImageHandle],
        thumbnail_image: Union[HeifImageHandle, AsyncHeifImageHandle],
    ) -> None:
        m = (
            master_image._handle
            if isinstance(master_image, AsyncHeifImageHandle)
            else master_image
        )
        t = (
            thumbnail_image._handle
            if isinstance(thumbnail_image, AsyncHeifImageHandle)
            else thumbnail_image
        )
        self._ctx.assign_thumbnail(m, t)

    async def assign_thumbnail_async(
        self,
        master_image: Union[HeifImageHandle, AsyncHeifImageHandle],
        thumbnail_image: Union[HeifImageHandle, AsyncHeifImageHandle],
    ) -> None:
        m = (
            master_image._handle
            if isinstance(master_image, AsyncHeifImageHandle)
            else master_image
        )
        t = (
            thumbnail_image._handle
            if isinstance(thumbnail_image, AsyncHeifImageHandle)
            else thumbnail_image
        )
        await _run_in_executor(self._executor, self._ctx.assign_thumbnail, m, t)

    def assign_auxiliary_image(
        self,
        master_image: Union[HeifImageHandle, AsyncHeifImageHandle],
        auxiliary_image: Union[HeifImageHandle, AsyncHeifImageHandle],
        auxiliary_type: str,
    ) -> None:
        m = (
            master_image._handle
            if isinstance(master_image, AsyncHeifImageHandle)
            else master_image
        )
        a = (
            auxiliary_image._handle
            if isinstance(auxiliary_image, AsyncHeifImageHandle)
            else auxiliary_image
        )
        self._ctx.assign_auxiliary_image(m, a, auxiliary_type)

    async def assign_auxiliary_image_async(
        self,
        master_image: Union[HeifImageHandle, AsyncHeifImageHandle],
        auxiliary_image: Union[HeifImageHandle, AsyncHeifImageHandle],
        auxiliary_type: str,
    ) -> None:
        m = (
            master_image._handle
            if isinstance(master_image, AsyncHeifImageHandle)
            else master_image
        )
        a = (
            auxiliary_image._handle
            if isinstance(auxiliary_image, AsyncHeifImageHandle)
            else auxiliary_image
        )
        await _run_in_executor(
            self._executor, self._ctx.assign_auxiliary_image, m, a, auxiliary_type
        )

    def set_primary_image(
        self, handle: Union[HeifImageHandle, AsyncHeifImageHandle]
    ) -> None:
        """Designate an image handle as the primary image of the context."""
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        self._ctx.set_primary_image(h)

    async def set_primary_image_async(
        self, handle: Union[HeifImageHandle, AsyncHeifImageHandle]
    ) -> None:
        """Asynchronously designate an image handle as the primary image of the context."""
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        await _run_in_executor(self._executor, self._ctx.set_primary_image, h)

    def set_major_brand(self, brand: str) -> None:
        """Set the major brand of the HEIF container (4-character FourCC)."""
        self._ctx.set_major_brand(brand)

    def add_compatible_brand(self, brand: str) -> None:
        """Add a compatible brand to the HEIF container (4-character FourCC)."""
        self._ctx.add_compatible_brand(brand)

    @property
    def has_sequence(self) -> bool:
        """Check if the context contains any image sequence tracks."""
        return self._ctx.has_sequence()

    def get_sequence_timescale(self) -> int:
        """Get the sequence timescale (ticks per second)."""
        return self._ctx.get_sequence_timescale()

    def get_sequence_duration(self) -> int:
        """Get the total sequence duration in ticks."""
        return self._ctx.get_sequence_duration()

    def get_number_of_sequence_tracks(self) -> int:
        """Get the number of sequence tracks."""
        return self._ctx.get_number_of_sequence_tracks()

    def get_sequence_track_ids(self) -> List[int]:
        """Get the list of sequence track IDs."""
        return self._ctx.get_sequence_track_ids()

    def get_track(self, track_id: int = 0) -> "AsyncHeifTrack":
        """Get a track wrapper (use track_id=0 for first visual track)."""
        track = self._ctx.get_track(track_id)
        return AsyncHeifTrack(track, executor=self._executor)

    async def get_track_async(self, track_id: int = 0) -> "AsyncHeifTrack":
        """Asynchronously get a track wrapper."""
        track = await _run_in_executor(self._executor, self._ctx.get_track, track_id)
        return AsyncHeifTrack(track, executor=self._executor)

    def add_visual_sequence_track(
        self,
        width: int,
        height: int,
        track_type: Union[HeifTrackType, int] = HeifTrackType.ImageSequence,
        timescale: int = 1000,
    ) -> "AsyncHeifTrack":
        """Add a visual sequence track to the context for encoding."""
        track = self._ctx.add_visual_sequence_track(
            width, height, track_type, timescale
        )
        return AsyncHeifTrack(track, executor=self._executor)

    async def add_visual_sequence_track_async(
        self,
        width: int,
        height: int,
        track_type: Union[HeifTrackType, int] = HeifTrackType.ImageSequence,
        timescale: int = 1000,
    ) -> "AsyncHeifTrack":
        """Asynchronously add a visual sequence track."""
        track = await _run_in_executor(
            self._executor,
            self._ctx.add_visual_sequence_track,
            width,
            height,
            track_type,
            timescale,
        )
        return AsyncHeifTrack(track, executor=self._executor)

    def set_sequence_timescale(self, timescale: int) -> None:
        """Set the sequence timescale (ticks per second)."""
        self._ctx.set_sequence_timescale(timescale)

    def set_number_of_sequence_repetitions(self, repetitions: int) -> None:
        """Set the repetition count for the sequence (0 = infinite)."""
        self._ctx.set_number_of_sequence_repetitions(repetitions)


class AsyncHeifTrack:
    """Async wrapper for HeifTrack (timed image sequences/animations)."""

    def __init__(
        self,
        track: HeifTrack,
        executor: Optional[concurrent.futures.Executor] = None,
    ):
        self._track = track
        self._executor = executor

    def __repr__(self) -> str:
        return repr(self._track).replace("HeifTrack", "AsyncHeifTrack")

    @property
    def id(self) -> int:
        return self._track.id

    @property
    def track_type(self) -> HeifTrackType:
        return self._track.track_type

    @property
    def timescale(self) -> int:
        return self._track.timescale

    @property
    def number_of_repetitions(self) -> int:
        return self._track.number_of_repetitions

    @property
    def resolution(self) -> tuple[int, int]:
        return self._track.resolution

    @property
    def has_alpha_channel(self) -> bool:
        return self._track.has_alpha_channel

    def rewind(self) -> None:
        """Rewind sequence track playback back to frame 0."""
        self._track.rewind()

    async def rewind_async(self) -> None:
        """Asynchronously rewind sequence track playback back to frame 0."""
        await _run_in_executor(self._executor, self._track.rewind)

    def encode_sequence_image(
        self,
        image: HeifImage,
        encoder: Union[HeifEncoder, "AsyncHeifEncoder"],
        save_alpha: bool = False,
    ) -> None:
        """Append a frame to the sequence track."""
        enc = encoder._encoder if isinstance(encoder, AsyncHeifEncoder) else encoder
        self._track.encode_sequence_image(image, enc, save_alpha)

    async def encode_sequence_image_async(
        self,
        image: HeifImage,
        encoder: Union[HeifEncoder, "AsyncHeifEncoder"],
        save_alpha: bool = False,
    ) -> None:
        """Asynchronously append a frame to the sequence track."""
        enc = encoder._encoder if isinstance(encoder, AsyncHeifEncoder) else encoder
        await _run_in_executor(
            self._executor,
            self._track.encode_sequence_image,
            image,
            enc,
            save_alpha,
        )

    def encode_end_of_sequence(
        self,
        encoder: Union[HeifEncoder, "AsyncHeifEncoder"],
    ) -> None:
        """Finalize the sequence track encoding."""
        enc = encoder._encoder if isinstance(encoder, AsyncHeifEncoder) else encoder
        self._track.encode_end_of_sequence(enc)

    async def encode_end_of_sequence_async(
        self,
        encoder: Union[HeifEncoder, "AsyncHeifEncoder"],
    ) -> None:
        """Asynchronously finalize the sequence track encoding."""
        enc = encoder._encoder if isinstance(encoder, AsyncHeifEncoder) else encoder
        await _run_in_executor(self._executor, self._track.encode_end_of_sequence, enc)

    def decode_next_image(
        self,
        colorspace: HeifColorspace = HeifColorspace.RGB,
        chroma: HeifChroma = HeifChroma.InterleavedRGB,
        options: Optional[HeifDecodingOptions] = None,
    ) -> Optional[HeifImage]:
        """Decode next image frame in sequence. Returns None at end of sequence."""
        return self._track.decode_next_image(colorspace, chroma, options)

    async def decode_next_image_async(
        self,
        colorspace: HeifColorspace = HeifColorspace.RGB,
        chroma: HeifChroma = HeifChroma.InterleavedRGB,
        options: Optional[HeifDecodingOptions] = None,
    ) -> Optional[HeifImage]:
        """Asynchronously decode next image frame in sequence."""
        return await _run_in_executor(
            self._executor,
            self._track.decode_next_image,
            colorspace,
            chroma,
            options,
        )


class AsyncHeifEncoder:
    """Async wrapper for HeifEncoder."""

    def __init__(
        self,
        format_or_descriptor,
        preset: str = "",
        executor: Optional[concurrent.futures.Executor] = None,
    ):
        self._encoder = HeifEncoder(format_or_descriptor, preset=preset)
        self._executor = executor

    def __repr__(self) -> str:
        return repr(self._encoder).replace("HeifEncoder", "AsyncHeifEncoder")

    def apply_preset(self, preset: str) -> None:
        self._encoder.apply_preset(preset)

    def has_parameter(self, name: str) -> bool:
        return self._encoder.has_parameter(name)

    def set_parameters(self, params: dict) -> None:
        self._encoder.set_parameters(params)

    async def encode_image(
        self,
        context: Union[HeifContext, AsyncHeifContext],
        image: HeifImage,
        preset: str = "",
        options: Optional[HeifEncodingOptions] = None,
    ) -> HeifImageHandle:
        """Asynchronously encode image."""
        ctx = context._ctx if isinstance(context, AsyncHeifContext) else context
        exec_pool = self._executor or getattr(context, "_executor", None)
        return await _run_in_executor(
            exec_pool, self._encoder.encode_image, ctx, image, preset, options
        )

    async def encode_thumbnail(
        self,
        context: Union[HeifContext, AsyncHeifContext],
        image: HeifImage,
        master_image: Union[HeifImageHandle, AsyncHeifImageHandle],
        bbox_size: int,
        options: Optional[HeifEncodingOptions] = None,
    ) -> Optional[HeifImageHandle]:
        """Asynchronously encode thumbnail image."""
        ctx = context._ctx if isinstance(context, AsyncHeifContext) else context
        m = (
            master_image._handle
            if isinstance(master_image, AsyncHeifImageHandle)
            else master_image
        )
        exec_pool = self._executor or getattr(context, "_executor", None)
        return await _run_in_executor(
            exec_pool,
            self._encoder.encode_thumbnail,
            ctx,
            image,
            m,
            bbox_size,
            options,
        )

    def set_lossy_quality(self, quality: int) -> None:
        self._encoder.set_lossy_quality(quality)

    def set_lossless(self, lossless: bool) -> None:
        self._encoder.set_lossless(lossless)

    def set_parameter(self, name: str, value: str) -> None:
        self._encoder.set_parameter(name, value)

    def get_parameter(self, name: str) -> str:
        return self._encoder.get_parameter(name)

    def set_integer_parameter(self, name: str, value: int) -> None:
        self._encoder.set_integer_parameter(name, value)

    def get_integer_parameter(self, name: str) -> int:
        return self._encoder.get_integer_parameter(name)

    def set_boolean_parameter(self, name: str, value: bool) -> None:
        self._encoder.set_boolean_parameter(name, value)

    def get_boolean_parameter(self, name: str) -> bool:
        return self._encoder.get_boolean_parameter(name)

    def set_string_parameter(self, name: str, value: str) -> None:
        self._encoder.set_string_parameter(name, value)

    def get_string_parameter(self, name: str) -> str:
        return self._encoder.get_string_parameter(name)

    @property
    def name(self) -> str:
        return self._encoder.name

    @property
    def parameters(self) -> Any:
        return self._encoder.parameters


