from ._pylibheif import (
    HeifErrorCode,
    HeifColorspace,
    HeifChroma,
    HeifChannel,
    HeifCompressionFormat,
    HeifError,
    HeifContext,
    HeifImageHandle,
    HeifPlane,
    HeifImage,
    HeifEncoderDescriptor,
    get_encoder_descriptors,
    HeifEncoder,
    __doc__,
)

import asyncio
from typing import Optional, Union, List

# Re-export all names from the C++ extension and async wrappers
__all__ = [
    "HeifErrorCode",
    "HeifColorspace",
    "HeifChroma",
    "HeifChannel",
    "HeifCompressionFormat",
    "HeifError",
    "HeifContext",
    "HeifImageHandle",
    "HeifPlane",
    "HeifImage",
    "HeifEncoderDescriptor",
    "get_encoder_descriptors",
    "HeifEncoder",
    "AsyncHeifContext",
    "AsyncHeifImageHandle",
    "AsyncHeifEncoder",
    "__doc__",
]


class AsyncHeifImageHandle:
    """Async wrapper for HeifImageHandle."""

    def __init__(self, handle: HeifImageHandle):
        self._handle = handle

    @property
    def width(self) -> int:
        return self._handle.width

    @property
    def height(self) -> int:
        return self._handle.height

    @property
    def has_alpha(self) -> bool:
        return self._handle.has_alpha

    async def decode(
        self,
        colorspace: HeifColorspace = HeifColorspace.RGB,
        chroma: HeifChroma = HeifChroma.InterleavedRGB,
    ) -> HeifImage:
        """Asynchronously decode the image."""
        return await asyncio.to_thread(self._handle.decode, colorspace, chroma)

    def get_metadata_block_ids(self, type_filter: str = "") -> List[str]:
        return self._handle.get_metadata_block_ids(type_filter)

    def get_metadata_block_type(self, id: str) -> str:
        return self._handle.get_metadata_block_type(id)

    def get_metadata_block(self, id: str) -> bytes:
        return self._handle.get_metadata_block(id)


class AsyncHeifContext:
    """Async wrapper for HeifContext."""

    def __init__(self, ctx: Optional[HeifContext] = None):
        self._ctx = ctx or HeifContext()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def read_from_file(self, filename: str) -> None:
        """Asynchronously read from file."""
        await asyncio.to_thread(self._ctx.read_from_file, filename)

    async def read_from_memory(self, data: bytes) -> None:
        """Asynchronously read from memory."""
        await asyncio.to_thread(self._ctx.read_from_memory, data)

    async def write_to_file(self, filename: str) -> None:
        """Asynchronously write to file."""
        await asyncio.to_thread(self._ctx.write_to_file, filename)

    async def write_to_bytes(self) -> bytes:
        """Asynchronously write to bytes."""
        return await asyncio.to_thread(self._ctx.write_to_bytes)

    def get_primary_image_handle(self) -> AsyncHeifImageHandle:
        """Get async wrapper for primary image handle."""
        handle = self._ctx.get_primary_image_handle()
        return AsyncHeifImageHandle(handle)

    def get_image_handle(self, id: int) -> AsyncHeifImageHandle:
        """Get async wrapper for specific image ID."""
        handle = self._ctx.get_image_handle(id)
        return AsyncHeifImageHandle(handle)

    def get_list_of_top_level_image_IDs(self) -> List[int]:
        return self._ctx.get_list_of_top_level_image_IDs()

    def add_exif_metadata(
        self, handle: Union[HeifImageHandle, AsyncHeifImageHandle], data: bytes
    ) -> None:
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        self._ctx.add_exif_metadata(h, data)

    def add_xmp_metadata(
        self, handle: Union[HeifImageHandle, AsyncHeifImageHandle], data: bytes
    ) -> None:
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        self._ctx.add_xmp_metadata(h, data)

    def add_generic_metadata(
        self,
        handle: Union[HeifImageHandle, AsyncHeifImageHandle],
        data: bytes,
        item_type: str,
        content_type: str = "",
    ) -> None:
        h = handle._handle if isinstance(handle, AsyncHeifImageHandle) else handle
        self._ctx.add_generic_metadata(h, data, item_type, content_type)

    def __getattr__(self, name):
        """Delegate attribute access to underlying context."""
        return getattr(self._ctx, name)


class AsyncHeifEncoder:
    """Async wrapper for HeifEncoder."""

    def __init__(self, format_or_descriptor):
        self._encoder = HeifEncoder(format_or_descriptor)

    async def encode_image(
        self,
        context: Union[HeifContext, AsyncHeifContext],
        image: HeifImage,
        preset: str = "",
    ) -> HeifImageHandle:
        """Asynchronously encode image."""
        ctx = context._ctx if isinstance(context, AsyncHeifContext) else context
        return await asyncio.to_thread(self._encoder.encode_image, ctx, image, preset)

    def set_lossy_quality(self, quality: int) -> None:
        self._encoder.set_lossy_quality(quality)

    def set_parameter(self, name: str, value: str) -> None:
        self._encoder.set_parameter(name, value)

    @property
    def name(self) -> str:
        return self._encoder.name
