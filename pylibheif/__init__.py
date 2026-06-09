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
    __doc__,
)

import asyncio
import weakref
from typing import Optional, Union, List


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
    "HeifEncoderParametersProxy",
    "AsyncHeifContext",
    "AsyncHeifImageHandle",
    "AsyncHeifEncoder",
    "__doc__",
]


class HeifEncoderParametersProxy:
    """Proxy class providing dict-like access to HeifEncoder parameters."""

    def __init__(self, encoder: HeifEncoder):
        self._encoder = encoder
        # Cache the metadata of parameters for quick lookup and local validation
        self._metadata = {p.name: p for p in encoder._list_parameters()}

    def __getitem__(self, name: str):
        if name not in self._metadata:
            raise KeyError(f"Parameter '{name}' not found on encoder '{self._encoder.name}'")
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
            raise KeyError(f"Parameter '{name}' not found on encoder '{self._encoder.name}'")

        param = self._metadata[name]
        if param.type == HeifEncoderParameterType.Integer:
            if not isinstance(value, (int, float)):
                raise TypeError(f"Parameter '{name}' requires an integer value, got {type(value)}")
            int_val = int(value)
            # Validate ranges/values if they exist
            if param.valid_integer_range is not None:
                min_v, max_v = param.valid_integer_range
                if not (min_v <= int_val <= max_v):
                    raise ValueError(f"Value {int_val} for parameter '{name}' is out of range [{min_v}, {max_v}]")
            if param.valid_integer_values is not None:
                if int_val not in param.valid_integer_values:
                    raise ValueError(f"Value {int_val} for parameter '{name}' is not in valid values {param.valid_integer_values}")
            self._encoder.set_integer_parameter(name, int_val)

        elif param.type == HeifEncoderParameterType.Boolean:
            if not isinstance(value, bool):
                raise TypeError(f"Parameter '{name}' requires a boolean value, got {type(value)}")
            self._encoder.set_boolean_parameter(name, value)

        elif param.type == HeifEncoderParameterType.String:
            str_val = str(value)
            if param.valid_string_values is not None:
                if str_val not in param.valid_string_values:
                    raise ValueError(f"Value '{str_val}' for parameter '{name}' is not in valid values {param.valid_string_values}")
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

def _get_encoder_parameters(encoder: HeifEncoder) -> HeifEncoderParametersProxy:
    try:
        if encoder not in _encoder_parameters_cache:
            _encoder_parameters_cache[encoder] = HeifEncoderParametersProxy(encoder)
        return _encoder_parameters_cache[encoder]
    except TypeError:
        # Fallback if not weak-referenceable
        return HeifEncoderParametersProxy(encoder)

HeifEncoder.parameters = property(_get_encoder_parameters)



class AsyncHeifImageHandle:
    """Async wrapper for HeifImageHandle."""

    def __init__(self, handle: HeifImageHandle):
        self._handle = handle

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
    def mastering_display_colour_volume(self) -> Optional[HeifMasteringDisplayColourVolume]:
        return self._handle.mastering_display_colour_volume

    @property
    def ambient_viewing_environment(self) -> Optional[HeifAmbientViewingEnvironment]:
        return self._handle.ambient_viewing_environment

    @property
    def color_profile_type(self) -> HeifColorProfileType:
        return self._handle.color_profile_type

    def get_raw_color_profile(self) -> bytes:
        return self._handle.get_raw_color_profile()

    def get_nclx_color_profile(self) -> Optional[HeifColorProfileNclx]:
        return self._handle.get_nclx_color_profile()

    async def decode(
        self,
        colorspace: HeifColorspace = HeifColorspace.RGB,
        chroma: HeifChroma = HeifChroma.InterleavedRGB,
        options: Optional[HeifDecodingOptions] = None,
    ) -> HeifImage:
        """Asynchronously decode the image."""
        return await asyncio.to_thread(self._handle.decode, colorspace, chroma, options)

    def get_metadata_block_ids(self, type_filter: str = "") -> List[int]:
        return self._handle.get_metadata_block_ids(type_filter)

    def get_metadata_block_type(self, id: int) -> str:
        return self._handle.get_metadata_block_type(id)

    def get_metadata_block(self, id: int) -> bytes:
        return self._handle.get_metadata_block(id)

    def get_auxiliary_image_ids(self, aux_key_mask: int = 0) -> List[int]:
        return self._handle.get_auxiliary_image_ids(aux_key_mask)

    def get_auxiliary_type(self) -> str:
        return self._handle.get_auxiliary_type()

    def get_auxiliary_image_handle(self, id: int) -> "AsyncHeifImageHandle":
        handle = self._handle.get_auxiliary_image_handle(id)
        return AsyncHeifImageHandle(handle)


class AsyncHeifContext:
    """Async wrapper for HeifContext."""

    def __init__(self, ctx: Optional[HeifContext] = None):
        self._ctx = ctx or HeifContext()

    def __repr__(self) -> str:
        return repr(self._ctx).replace("HeifContext", "AsyncHeifContext")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the context and release resources."""
        self._ctx.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()

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


class AsyncHeifEncoder:
    """Async wrapper for HeifEncoder."""

    def __init__(self, format_or_descriptor):
        self._encoder = HeifEncoder(format_or_descriptor)

    def __repr__(self) -> str:
        return repr(self._encoder).replace("HeifEncoder", "AsyncHeifEncoder")

    async def encode_image(
        self,
        context: Union[HeifContext, AsyncHeifContext],
        image: HeifImage,
        preset: str = "",
        options: Optional[HeifEncodingOptions] = None,
    ) -> HeifImageHandle:
        """Asynchronously encode image."""
        ctx = context._ctx if isinstance(context, AsyncHeifContext) else context
        return await asyncio.to_thread(self._encoder.encode_image, ctx, image, preset, options)

    def set_lossy_quality(self, quality: int) -> None:
        self._encoder.set_lossy_quality(quality)

    def set_lossless(self, lossless: bool) -> None:
        self._encoder.set_lossless(lossless)

    def set_parameter(self, name: str, value: str) -> None:
        self._encoder.set_parameter(name, value)

    @property
    def name(self) -> str:
        return self._encoder.name

    @property
    def parameters(self) -> HeifEncoderParametersProxy:
        return self._encoder.parameters

