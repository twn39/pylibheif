from ._pylibheif import (
    HeifErrorCode,
    HeifColorspace,
    HeifChroma,
    HeifChannel,
    HeifCompressionFormat,
    HeifError,
    HeifInputDoesNotExistError,
    HeifInvalidInputError,
    HeifUnsupportedFiletypeError,
    HeifUnsupportedFeatureError,
    HeifUsageError,
    HeifMemoryAllocationError,
    HeifEncodingError,
    HeifColorProfileDoesNotExistError,
    HeifContext,
    HeifImageHandle,
    HeifImage,
    HeifEncoderDescriptor,
    get_encoder_descriptors,
    HeifEncoder,
    HeifContentLightLevel,
    HeifMasteringDisplayColourVolume,
    HeifAmbientViewingEnvironment,
    HeifColorProfileType,
    HeifColorPrimaries,
    HeifTransferCharacteristics,
    HeifMatrixCoefficients,
    HeifColorProfileNclx,
    HeifDecodingOptions,
    HeifOrientation,
    HeifChromaDownsamplingAlgorithm,
    HeifChromaUpsamplingAlgorithm,
    HeifEncodingOptions,
    AUX_IMAGE_FILTER_OMIT_ALPHA,
    AUX_IMAGE_FILTER_OMIT_DEPTH,
    HeifEncoderParameter,
    HeifEncoderParameterType,
    HeifPlaneLayout,
    HeifImageLayout,
    HeifImageTiling,
    HeifDepthRepresentationInfo,
    get_default_num_threads,
    set_default_num_threads,
    get_default_encoder_preset,
    set_default_encoder_preset,
    get_libheif_version,
    get_libheif_version_number,
    __doc__,
)

__version__ = "1.23.1"

import atexit
import asyncio
import concurrent.futures
import math
import os
import weakref
import threading
from typing import Optional, Union, List, Any


# Re-export all names from the C++ extension and async wrappers
__all__ = [
    "HeifErrorCode",
    "HeifColorspace",
    "HeifChroma",
    "HeifChannel",
    "HeifCompressionFormat",
    "HeifError",
    "HeifInputDoesNotExistError",
    "HeifInvalidInputError",
    "HeifUnsupportedFiletypeError",
    "HeifUnsupportedFeatureError",
    "HeifUsageError",
    "HeifMemoryAllocationError",
    "HeifEncodingError",
    "HeifColorProfileDoesNotExistError",
    "HeifContext",
    "HeifImageHandle",
    "HeifImage",
    "HeifEncoderDescriptor",
    "get_encoder_descriptors",
    "HeifEncoder",
    "HeifContentLightLevel",
    "HeifMasteringDisplayColourVolume",
    "HeifAmbientViewingEnvironment",
    "HeifColorProfileType",
    "HeifColorPrimaries",
    "HeifTransferCharacteristics",
    "HeifMatrixCoefficients",
    "HeifColorProfileNclx",
    "HeifDecodingOptions",
    "HeifOrientation",
    "HeifChromaDownsamplingAlgorithm",
    "HeifChromaUpsamplingAlgorithm",
    "HeifEncodingOptions",
    "AUX_IMAGE_FILTER_OMIT_ALPHA",
    "AUX_IMAGE_FILTER_OMIT_DEPTH",
    "HeifEncoderParameter",
    "HeifEncoderParameterType",
    "HeifPlaneLayout",
    "HeifImageLayout",
    "HeifImageTiling",
    "HeifDepthRepresentationInfo",
    "HeifEncoderParametersProxy",
    "AsyncHeifContext",
    "AsyncHeifImageHandle",
    "AsyncHeifEncoder",
    "get_default_num_threads",
    "set_default_num_threads",
    "get_default_encoder_preset",
    "set_default_encoder_preset",
    "get_libheif_version",
    "get_libheif_version_number",
    "get_default_codec_executor",
    "set_default_codec_executor",
    "shutdown_default_codec_executor",
    "to_pillow",
    "from_pillow",
    "register_pillow_opener",
    "unregister_pillow_opener",
    "__version__",
    "__doc__",
]


def _heif_error_str(self: HeifError) -> str:
    code_name = getattr(self, "code_name", "Unknown")
    code_val = getattr(self, "code", -1)
    subcode_val = getattr(self, "subcode", -1)
    msg = Exception.__str__(self)
    return f"[{self.__class__.__name__}] {code_name} (code={code_val}, subcode={subcode_val}): {msg}"


def _heif_error_repr(self: HeifError) -> str:
    code_name = getattr(self, "code_name", "Unknown")
    code_val = getattr(self, "code", -1)
    subcode_val = getattr(self, "subcode", -1)
    msg = Exception.__str__(self)
    return f"<{self.__class__.__name__} code_name='{code_name}' code={code_val} subcode={subcode_val} message={msg!r}>"


setattr(HeifError, "__str__", _heif_error_str)
setattr(HeifError, "__repr__", _heif_error_repr)


class HeifEncoderParametersProxy:
    """Proxy class providing dict-like access to HeifEncoder parameters."""

    def __init__(self, encoder: HeifEncoder):
        self._encoder_ref = weakref.ref(encoder)
        # Cache the metadata of parameters for quick lookup and local validation
        self._metadata = {p.name: p for p in encoder._list_parameters()}

    @property
    def _encoder(self) -> HeifEncoder:
        enc = self._encoder_ref()
        if enc is None:
            raise ReferenceError(
                "The underlying HeifEncoder has been garbage collected"
            )
        return enc

    def __getitem__(self, name: str):
        if name not in self._metadata:
            raise KeyError(
                f"Parameter '{name}' not found on encoder '{self._encoder.name}'"
            )
        param = self._metadata[name]
        if param.type == HeifEncoderParameterType.Integer:
            return self._encoder.get_integer_parameter(name)
        elif param.type == HeifEncoderParameterType.Boolean:
            return self._encoder.get_boolean_parameter(name)
        elif param.type == HeifEncoderParameterType.String:
            return self._encoder.get_string_parameter(name)
        else:
            return self._encoder.get_parameter(name)

    def __setitem__(self, name: str, value):
        if name not in self._metadata:
            # Allow pass-through for prefixed parameters (e.g. x265:ctu)
            if ":" in name:
                self._encoder.set_parameter(name, str(value))
                return
            raise KeyError(
                f"Parameter '{name}' not found on encoder '{self._encoder.name}'"
            )

        param = self._metadata[name]
        if param.type == HeifEncoderParameterType.Integer:
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"Parameter '{name}' requires an integer value, got {type(value)}"
                )
            int_val = int(value)
            # Validate ranges/values if they exist
            if param.valid_integer_range is not None:
                min_v, max_v = param.valid_integer_range
                if not (min_v <= int_val <= max_v):
                    raise ValueError(
                        f"Value {int_val} for parameter '{name}' is out of range [{min_v}, {max_v}]"
                    )
            if param.valid_integer_values is not None:
                if int_val not in param.valid_integer_values:
                    raise ValueError(
                        f"Value {int_val} for parameter '{name}' is not in valid values {param.valid_integer_values}"
                    )
            self._encoder.set_integer_parameter(name, int_val)

        elif param.type == HeifEncoderParameterType.Boolean:
            if not isinstance(value, bool):
                raise TypeError(
                    f"Parameter '{name}' requires a boolean value, got {type(value)}"
                )
            self._encoder.set_boolean_parameter(name, value)

        elif param.type == HeifEncoderParameterType.String:
            str_val = str(value)
            if param.valid_string_values is not None:
                if str_val not in param.valid_string_values:
                    raise ValueError(
                        f"Value '{str_val}' for parameter '{name}' is not in valid values {param.valid_string_values}"
                    )
            self._encoder.set_string_parameter(name, str_val)

    def __contains__(self, name: str) -> bool:
        return name in self._metadata or ":" in name

    def keys(self):
        return self._metadata.keys()

    def values(self):
        return [self._metadata[k] for k in self._metadata]

    def items(self):
        return [(k, self._metadata[k]) for k in self._metadata]

    def __len__(self) -> int:
        return len(self._metadata)

    def __iter__(self):
        return iter(self._metadata)

    def __repr__(self) -> str:
        items_repr = ", ".join(f"'{k}': {self[k]}" for k in self.keys())
        return f"HeifEncoderParameters({{{items_repr}}})"


_encoder_parameters_cache = weakref.WeakKeyDictionary()
_encoder_parameters_lock = threading.Lock()


def _get_encoder_parameters(encoder: HeifEncoder) -> HeifEncoderParametersProxy:
    try:
        with _encoder_parameters_lock:
            if encoder not in _encoder_parameters_cache:
                _encoder_parameters_cache[encoder] = HeifEncoderParametersProxy(encoder)
            return _encoder_parameters_cache[encoder]
    except TypeError:
        # Fallback if not weak-referenceable
        return HeifEncoderParametersProxy(encoder)


HeifEncoder.parameters = property(_get_encoder_parameters)  # type: ignore
HeifImageHandle.thumbnails = property(  # type: ignore
    lambda self: [self.get_thumbnail(tid) for tid in self.get_thumbnail_ids()]
)


def _detect_usable_cpu_count() -> int:
    """Detect the number of usable CPU cores, taking into account cgroups quotas and affinities."""
    if hasattr(os, "process_cpu_count"):
        try:
            cnt = os.process_cpu_count()
            if cnt is not None and cnt > 0:
                return cnt
        except Exception:
            pass

    # Check Linux cgroups v2 quota (/sys/fs/cgroup/cpu.max)
    try:
        with open("/sys/fs/cgroup/cpu.max", "r", encoding="utf-8") as f:
            quota_s, period_s = f.read().strip().split()
            if quota_s != "max":
                quota = int(quota_s)
                period = int(period_s)
                if quota > 0 and period > 0:
                    return max(1, math.ceil(quota / period))
    except (OSError, ValueError):
        pass

    # Check Linux cgroups v1 quota (/sys/fs/cgroup/cpu/cpu.cfs_quota_us)
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "r", encoding="utf-8") as fq:
            quota = int(fq.read().strip())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "r", encoding="utf-8") as fp:
            period = int(fp.read().strip())
        if quota > 0 and period > 0:
            return max(1, math.ceil(quota / period))
    except (OSError, ValueError):
        pass

    return max(1, os.cpu_count() or 1)


_default_codec_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
_default_codec_executor_lock = threading.Lock()


def get_default_codec_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Get or lazily initialize the dedicated thread pool executor for CPU-bound codec operations."""
    global _default_codec_executor
    if _default_codec_executor is None:
        with _default_codec_executor_lock:
            if _default_codec_executor is None:
                usable = _detect_usable_cpu_count()
                workers = max(1, usable // 2)
                _default_codec_executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=workers,
                    thread_name_prefix="pylibheif-codec",
                )
    return _default_codec_executor


def set_default_codec_executor(
    executor: Optional[concurrent.futures.ThreadPoolExecutor],
) -> None:
    """Set or replace the default codec executor.

    If an existing internal executor was active, it is cleanly shut down.
    """
    global _default_codec_executor
    with _default_codec_executor_lock:
        old_executor = _default_codec_executor
        _default_codec_executor = executor
    if old_executor is not None and old_executor is not executor:
        try:
            old_executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            old_executor.shutdown(wait=False)


def shutdown_default_codec_executor(
    wait: bool = False, cancel_futures: bool = True
) -> None:
    """Explicitly shut down the dedicated codec thread pool executor."""
    global _default_codec_executor
    with _default_codec_executor_lock:
        executor = _default_codec_executor
        _default_codec_executor = None
    if executor is not None:
        try:
            executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        except TypeError:
            executor.shutdown(wait=wait)


atexit.register(shutdown_default_codec_executor, wait=False, cancel_futures=True)


async def _run_in_executor(
    executor: Optional[concurrent.futures.Executor], func, *args
):
    exec_to_use = executor if executor is not None else get_default_codec_executor()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(exec_to_use, func, *args)


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
    ) -> HeifImage:
        """Asynchronously decode the image."""
        return await _run_in_executor(
            self._executor,
            self._handle.decode,
            colorspace,
            chroma,
            options,
            num_threads,
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
    def has_gain_map(self) -> bool:
        return getattr(self._handle, "has_gain_map", False)

    def get_gain_map_handle(self) -> "AsyncHeifImageHandle":
        handle = self._handle.get_gain_map_handle()
        return AsyncHeifImageHandle(handle, executor=self._executor)

    async def get_gain_map_handle_async(self) -> "AsyncHeifImageHandle":
        handle = await _run_in_executor(
            self._executor, self._handle.get_gain_map_handle
        )
        return AsyncHeifImageHandle(handle, executor=self._executor)

    async def decode_depth(self) -> Any:
        return await _run_in_executor(self._executor, self._handle.decode_depth)


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
        data: bytes,
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

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def read_from_file(self, filename: str) -> None:
        """Asynchronously read from file."""
        await _run_in_executor(self._executor, self._ctx.read_from_file, filename)

    async def read_from_memory(self, data: bytes) -> None:
        """Asynchronously read from memory."""
        await _run_in_executor(self._executor, self._ctx.read_from_memory, data)

    async def read_from_stream(self, stream: Any) -> None:
        """Asynchronously read from a Python file-like stream object."""
        await _run_in_executor(self._executor, self._ctx.read_from_stream, stream)

    async def write_to_file(self, filename: str) -> None:
        """Asynchronously write to file."""
        await _run_in_executor(self._executor, self._ctx.write_to_file, filename)

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

    def get_image_handle(self, id: int) -> AsyncHeifImageHandle:
        """Get async wrapper for specific image ID."""
        handle = self._ctx.get_image_handle(id)
        return AsyncHeifImageHandle(handle, executor=self._executor)

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


# --- Pillow (PIL) Interoperability ---


def to_pillow(
    source: Any,
    convert_hdr_to_8bit: bool = True,
    options: Optional[HeifDecodingOptions] = None,
    num_threads: Optional[int] = None,
) -> Any:
    """Convert a HeifImage or HeifImageHandle into a Pillow Image."""
    from .pillow.convert import to_pillow as _to_pillow

    return _to_pillow(
        source,
        convert_hdr_to_8bit=convert_hdr_to_8bit,
        options=options,
        num_threads=num_threads,
    )


def from_pillow(pil_image: Any, bit_depth: int = 8) -> Any:
    """Convert a Pillow Image into a pylibheif HeifImage."""
    from .pillow.convert import from_pillow as _from_pillow

    img, _ = _from_pillow(pil_image, bit_depth=bit_depth)
    return img


def register_pillow_opener() -> None:
    """Register pylibheif as a HEIF/AVIF image opener in Pillow."""
    from .pillow.plugin import register_heif_opener

    register_heif_opener()


def unregister_pillow_opener() -> None:
    """Unregister pylibheif handler from Pillow."""
    from .pillow.plugin import unregister_heif_opener

    unregister_heif_opener()


# Attach convenience methods to C++ classes
setattr(HeifImageHandle, "to_pillow", to_pillow)
setattr(HeifImage, "to_pillow", to_pillow)
setattr(HeifImage, "from_pillow", staticmethod(from_pillow))


def _handle_get_gain_map_ids(self: HeifImageHandle) -> List[int]:
    """Find all auxiliary image IDs corresponding to HDR Gain Maps."""
    gain_ids = []
    for aid in self.get_auxiliary_image_ids():
        try:
            aux_handle = self.get_auxiliary_image_handle(aid)
            atype = aux_handle.get_auxiliary_type()
            if "gainmap" in atype.lower() or "21496" in atype:
                gain_ids.append(aid)
        except Exception:
            pass
    return gain_ids


def _handle_has_gain_map(self: HeifImageHandle) -> bool:
    return len(_handle_get_gain_map_ids(self)) > 0


def _handle_get_gain_map_handle(self: HeifImageHandle) -> HeifImageHandle:
    ids = _handle_get_gain_map_ids(self)
    if not ids:
        raise ValueError("Image handle does not contain a Gain Map")
    return self.get_auxiliary_image_handle(ids[0])


def _handle_decode_depth(self: HeifImageHandle) -> Any:
    """Decode primary depth image and return as a 2D numpy array."""
    depth_handle = self.get_primary_depth_image_handle()
    decoded = depth_handle.decode(HeifColorspace.Monochrome, HeifChroma.Monochrome)
    plane = decoded.get_plane(HeifChannel.Y)
    import numpy as np

    return np.asarray(plane)


setattr(HeifImageHandle, "gain_map_ids", property(_handle_get_gain_map_ids))
setattr(HeifImageHandle, "has_gain_map", property(_handle_has_gain_map))
setattr(HeifImageHandle, "get_gain_map_handle", _handle_get_gain_map_handle)
setattr(HeifImageHandle, "decode_depth", _handle_decode_depth)
