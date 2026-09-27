"""Python bindings for libheif using nanobind."""

from __future__ import annotations

# Native C++ extension exports
from ._pylibheif import (
    AUX_IMAGE_FILTER_OMIT_ALPHA,
    AUX_IMAGE_FILTER_OMIT_DEPTH,
    HeifAmbientViewingEnvironment,
    HeifChannel,
    HeifChroma,
    HeifChromaDownsamplingAlgorithm,
    HeifChromaUpsamplingAlgorithm,
    HeifColorPrimaries,
    HeifColorProfileDoesNotExistError,
    HeifColorProfileNclx,
    HeifColorProfileType,
    HeifColorspace,
    HeifCompressionFormat,
    HeifContentLightLevel,
    HeifContext,
    HeifDecodingOptions,
    HeifDepthRepresentationInfo,
    HeifEncoder,
    HeifEncoderDescriptor,
    HeifEncoderParameter,
    HeifEncoderParameterType,
    HeifEncodingError,
    HeifEncodingOptions,
    HeifError,
    HeifErrorCode,
    HeifImage,
    HeifImageHandle,
    HeifImageLayout,
    HeifImageTiling,
    HeifInputDoesNotExistError,
    HeifInvalidInputError,
    HeifMasteringDisplayColourVolume,
    HeifMatrixCoefficients,
    HeifMemoryAllocationError,
    HeifOrientation,
    HeifPlaneLayout,
    HeifTrack,
    HeifTrackType,
    HeifTransferCharacteristics,
    HeifUnsupportedFeatureError,
    HeifUnsupportedFiletypeError,
    HeifUsageError,
    get_default_encoder_preset,
    get_default_num_threads,
    get_encoder_descriptors,
    get_libheif_version,
    get_libheif_version_number,
    set_default_encoder_preset,
    set_default_num_threads,
)

__version__ = "1.24.0"

# Concurrency & thread budgeting
from ._concurrency import (
    ConcurrencyBudget,
    _detect_usable_cpu_count as _detect_usable_cpu_count,
    _run_in_executor as _run_in_executor,
    get_concurrency_budget,
    get_default_codec_executor,
    set_default_codec_executor,
    shutdown_default_codec_executor,
)

# Encoder parameters proxy
from ._proxy import (
    HeifEncoderParametersProxy,
    _encoder_parameters_cache as _encoder_parameters_cache,
    _encoder_parameters_lock as _encoder_parameters_lock,
    get_encoder_parameters as get_encoder_parameters,
)

# Async coroutines API
from ._async import (
    AsyncHeifContext,
    AsyncHeifEncoder,
    AsyncHeifImageHandle,
    AsyncHeifTrack,
)

# Depth map & representation
from .depth import (
    AsyncDepthMap,
    DepthMap,
    DepthRepresentationType,
    extract_depth_map,
    extract_portrait_matte,
)

# Gain map & HDR metadata
from .gain_map import (
    AsyncGainMap,
    GainMap,
    GainMapMetadata,
    URN_GAIN_MAP_APPLE,
    URN_GAIN_MAP_ISO_21496_1,
    URN_PORTRAIT_MATTE_APPLE,
    extract_gain_map,
    generate_gain_map_xmp,
    linear_to_pq,
    linear_to_srgb,
    parse_gain_map_metadata,
    reconstruct_hdr,
    srgb_to_linear,
)

# Color management & profiles
from .color import (
    ADOBE_RGB_ICC_BYTES,
    DISPLAY_P3_ICC_BYTES,
    REC2020_ICC_BYTES,
    SRGB_ICC_BYTES,
    RenderingIntent,
    get_profile_info,
    nclx_to_icc_profile,
    resolve_profile_bytes,
    transform_colorspace,
)

# Pillow plugin & converters
from ._extensions import (
    from_pillow,
    install_handle_extensions,
    register_pillow_opener,
    to_pillow,
    unregister_pillow_opener,
)

# Patch exception formatting and attach dynamic handle extensions
from ._errors import patch_error_formatting

patch_error_formatting()
install_handle_extensions()

# Complete public API re-exports
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
    "HeifTrack",
    "HeifTrackType",
    "AsyncHeifContext",
    "AsyncHeifImageHandle",
    "AsyncHeifEncoder",
    "AsyncHeifTrack",
    "get_default_num_threads",
    "set_default_num_threads",
    "get_default_encoder_preset",
    "set_default_encoder_preset",
    "get_libheif_version",
    "get_libheif_version_number",
    "get_default_codec_executor",
    "set_default_codec_executor",
    "shutdown_default_codec_executor",
    "ConcurrencyBudget",
    "get_concurrency_budget",
    "to_pillow",
    "from_pillow",
    "register_pillow_opener",
    "unregister_pillow_opener",
    "DepthMap",
    "AsyncDepthMap",
    "DepthRepresentationType",
    "extract_depth_map",
    "extract_portrait_matte",
    "GainMap",
    "AsyncGainMap",
    "extract_gain_map",
    "GainMapMetadata",
    "parse_gain_map_metadata",
    "generate_gain_map_xmp",
    "srgb_to_linear",
    "linear_to_srgb",
    "linear_to_pq",
    "reconstruct_hdr",
    "URN_GAIN_MAP_ISO_21496_1",
    "URN_GAIN_MAP_APPLE",
    "URN_PORTRAIT_MATTE_APPLE",
    "DISPLAY_P3_ICC_BYTES",
    "SRGB_ICC_BYTES",
    "ADOBE_RGB_ICC_BYTES",
    "REC2020_ICC_BYTES",
    "RenderingIntent",
    "get_profile_info",
    "nclx_to_icc_profile",
    "resolve_profile_bytes",
    "transform_colorspace",
    "__version__",
    "__doc__",
]
