"""Python bindings for libheif using nanobind"""

import enum
import numpy
from typing import overload, TYPE_CHECKING

if TYPE_CHECKING:
    from pylibheif import HeifEncoderParametersProxy

class HeifErrorCode(enum.Enum):
    Ok = 0

    InputDoesNotExist = 1

    InvalidInput = 2

    UnsupportedFiletype = 3

    UnsupportedFeature = 4

    UsageError = 5

    MemoryAllocationError = 6

    DecoderPluginError = 7

    EncoderPluginError = 8

    EncodingError = 9

    ColorProfileDoesNotExist = 10

Ok: HeifErrorCode = HeifErrorCode.Ok

InputDoesNotExist: HeifErrorCode = HeifErrorCode.InputDoesNotExist

InvalidInput: HeifErrorCode = HeifErrorCode.InvalidInput

UnsupportedFiletype: HeifErrorCode = HeifErrorCode.UnsupportedFiletype

UnsupportedFeature: HeifErrorCode = HeifErrorCode.UnsupportedFeature

UsageError: HeifErrorCode = HeifErrorCode.UsageError

MemoryAllocationError: HeifErrorCode = HeifErrorCode.MemoryAllocationError

DecoderPluginError: HeifErrorCode = HeifErrorCode.DecoderPluginError

EncoderPluginError: HeifErrorCode = HeifErrorCode.EncoderPluginError

EncodingError: HeifErrorCode = HeifErrorCode.EncodingError

ColorProfileDoesNotExist: HeifErrorCode = HeifErrorCode.ColorProfileDoesNotExist

class HeifColorspace(enum.Enum):
    Undefined = 99

    YCbCr = 0

    RGB = 1

    Monochrome = 2

YCbCr: HeifColorspace = HeifColorspace.YCbCr

RGB: HeifColorspace = HeifColorspace.RGB

class HeifChroma(enum.Enum):
    Undefined = 99

    Monochrome = 0

    C420 = 1

    C422 = 2

    C444 = 3

    InterleavedRGB = 10

    InterleavedRGBA = 11

    InterleavedRRGGBB_BE = 12

    InterleavedRRGGBBAA_BE = 13

    InterleavedRRGGBB_LE = 14

    InterleavedRRGGBBAA_LE = 15

C420: HeifChroma = HeifChroma.C420

C422: HeifChroma = HeifChroma.C422

C444: HeifChroma = HeifChroma.C444

InterleavedRGB: HeifChroma = HeifChroma.InterleavedRGB

InterleavedRGBA: HeifChroma = HeifChroma.InterleavedRGBA

InterleavedRRGGBB_BE: HeifChroma = HeifChroma.InterleavedRRGGBB_BE

InterleavedRRGGBBAA_BE: HeifChroma = HeifChroma.InterleavedRRGGBBAA_BE

InterleavedRRGGBB_LE: HeifChroma = HeifChroma.InterleavedRRGGBB_LE

InterleavedRRGGBBAA_LE: HeifChroma = HeifChroma.InterleavedRRGGBBAA_LE

class HeifChannel(enum.Enum):
    Y = 0

    Cb = 1

    Cr = 2

    R = 3

    G = 4

    B = 5

    Alpha = 6

    Interleaved = 10

Y: HeifChannel = HeifChannel.Y

Cb: HeifChannel = HeifChannel.Cb

Cr: HeifChannel = HeifChannel.Cr

R: HeifChannel = HeifChannel.R

G: HeifChannel = HeifChannel.G

B: HeifChannel = HeifChannel.B

Alpha: HeifChannel = HeifChannel.Alpha

Interleaved: HeifChannel = HeifChannel.Interleaved

class HeifCompressionFormat(enum.Enum):
    Undefined = 0

    HEVC = 1

    AVC = 2

    JPEG = 3

    AV1 = 4

    JPEG2000 = 7

HEVC: HeifCompressionFormat = HeifCompressionFormat.HEVC

AVC: HeifCompressionFormat = HeifCompressionFormat.AVC

JPEG: HeifCompressionFormat = HeifCompressionFormat.JPEG

AV1: HeifCompressionFormat = HeifCompressionFormat.AV1

JPEG2000: HeifCompressionFormat = HeifCompressionFormat.JPEG2000

Undefined: HeifCompressionFormat = HeifCompressionFormat.Undefined

Monochrome: HeifChroma = HeifChroma.Monochrome

class HeifColorProfileType(enum.Enum):
    NotPresent = 0
    Nclx = 1852009592
    RICC = 1919247171
    Prof = 1886547814

class HeifColorPrimaries(enum.Enum):
    ITU_R_BT_709_5 = 1
    Unspecified = 2
    ITU_R_BT_470_6_System_M = 4
    ITU_R_BT_470_6_System_B_G = 5
    ITU_R_BT_601_6 = 6
    SMPTE_240M = 7
    GenericFilm = 8
    ITU_R_BT_2020_2_and_2100_0 = 9
    SMPTE_ST_428_1 = 10
    SMPTE_RP_431_2 = 11
    SMPTE_EG_432_1 = 12
    EBU_Tech_3213_E = 22

class HeifTransferCharacteristics(enum.Enum):
    ITU_R_BT_709_5 = 1
    Unspecified = 2
    ITU_R_BT_470_6_System_M = 4
    ITU_R_BT_470_6_System_B_G = 5
    ITU_R_BT_601_6 = 6
    SMPTE_240M = 7
    Linear = 8
    Logarithmic_100 = 9
    Logarithmic_100_sqrt10 = 10
    IEC_61966_2_4 = 11
    ITU_R_BT_1361 = 12
    IEC_61966_2_1 = 13
    ITU_R_BT_2020_2_10bit = 14
    ITU_R_BT_2020_2_12bit = 15
    ITU_R_BT_2100_0_PQ = 16
    SMPTE_ST_428_1 = 17
    ITU_R_BT_2100_0_HLG = 18

class HeifMatrixCoefficients(enum.Enum):
    RGB_GBR = 0
    ITU_R_BT_709_5 = 1
    Unspecified = 2
    US_FCC_T47 = 4
    ITU_R_BT_470_6_System_B_G = 5
    ITU_R_BT_601_6 = 6
    SMPTE_240M = 7
    YCgCo = 8
    ITU_R_BT_2020_2_non_constant_luminance = 9
    ITU_R_BT_2020_2_constant_luminance = 10
    SMPTE_ST_2085 = 11
    Chromaticity_derived_non_constant_luminance = 12
    Chromaticity_derived_constant_luminance = 13
    ICtCp = 14

class HeifColorProfileNclx:
    color_primaries: HeifColorPrimaries
    transfer_characteristics: HeifTransferCharacteristics
    matrix_coefficients: HeifMatrixCoefficients
    full_range_flag: bool
    color_primary_red_x: float
    color_primary_red_y: float
    color_primary_green_x: float
    color_primary_green_y: float
    color_primary_blue_x: float
    color_primary_blue_y: float
    color_primary_white_x: float
    color_primary_white_y: float
    def __init__(
        self,
        color_primaries: HeifColorPrimaries,
        transfer_characteristics: HeifTransferCharacteristics,
        matrix_coefficients: HeifMatrixCoefficients,
        full_range_flag: bool,
    ) -> None: ...

class HeifError(Exception):
    pass

class HeifInputDoesNotExistError(HeifError):
    pass

class HeifInvalidInputError(HeifError):
    pass

class HeifUnsupportedFiletypeError(HeifError):
    pass

class HeifUnsupportedFeatureError(HeifError):
    pass

class HeifUsageError(HeifError):
    pass

class HeifMemoryAllocationError(HeifError):
    pass

class HeifEncodingError(HeifError):
    pass

class HeifColorProfileDoesNotExistError(HeifError):
    pass

class HeifContentLightLevel:
    max_content_light_level: int
    max_pic_average_light_level: int
    def __init__(
        self, max_content_light_level: int = 0, max_pic_average_light_level: int = 0
    ) -> None: ...

class HeifMasteringDisplayColourVolume:
    red_primary: tuple[float, float]
    green_primary: tuple[float, float]
    blue_primary: tuple[float, float]
    white_point: tuple[float, float]
    max_luminance: float
    min_luminance: float
    def __init__(
        self,
        red_primary: tuple[float, float] = (0.0, 0.0),
        green_primary: tuple[float, float] = (0.0, 0.0),
        blue_primary: tuple[float, float] = (0.0, 0.0),
        white_point: tuple[float, float] = (0.0, 0.0),
        max_luminance: float = 0.0,
        min_luminance: float = 0.0,
    ) -> None: ...

class HeifAmbientViewingEnvironment:
    ambient_illumination: float
    ambient_light: tuple[float, float]
    def __init__(
        self,
        ambient_illumination: float = 0.0,
        ambient_light: tuple[float, float] = (0.0, 0.0),
    ) -> None: ...

class HeifDecodingOptions:
    ignore_transformations: bool
    convert_hdr_to_8bit: bool
    strict_decoding: bool
    decoder_id: str
    num_codec_threads: int
    autocorrect_broken_input: bool
    output_image_nclx_profile_passthrough: bool
    def __init__(self) -> None: ...

class HeifOrientation(enum.Enum):
    Normal = 1
    FlipHorizontally = 2
    Rotate180 = 3
    FlipVertically = 4
    Rotate90CwThenFlipHorizontally = 5
    Rotate90Cw = 6
    Rotate90CwThenFlipVertically = 7
    Rotate270Cw = 8

class HeifChromaDownsamplingAlgorithm(enum.Enum):
    NearestNeighbor = 1
    Average = 2
    SharpYuv = 3

class HeifChromaUpsamplingAlgorithm(enum.Enum):
    NearestNeighbor = 1
    Bilinear = 2

class HeifEncodingOptions:
    save_alpha_channel: bool
    save_two_colr_boxes_when_ICC_and_nclx_available: bool
    macOS_compatibility_workaround_no_nclx_profile: bool
    image_orientation: HeifOrientation
    prefer_uncC_short_form: bool
    preferred_chroma_downsampling_algorithm: HeifChromaDownsamplingAlgorithm
    preferred_chroma_upsampling_algorithm: HeifChromaUpsamplingAlgorithm
    only_use_preferred_chroma_algorithm: bool
    def __init__(self) -> None: ...

class HeifContext:
    def __init__(self) -> None: ...
    def close(self) -> None: ...
    def read_from_file(self, arg: str, /) -> None: ...
    def read_from_memory(self, arg: bytes, /) -> None: ...
    def get_primary_image_handle(self) -> HeifImageHandle: ...
    def get_list_of_top_level_image_IDs(self) -> list[int]: ...
    def get_image_handle(self, arg: int, /) -> HeifImageHandle: ...
    def write_to_file(self, arg: str, /) -> None: ...
    def write_to_bytes(self) -> bytes: ...
    def add_exif_metadata(self, handle: HeifImageHandle, data: bytes) -> None:
        """Add EXIF metadata to an image. The data should be raw EXIF bytes."""

    def add_xmp_metadata(self, handle: HeifImageHandle, data: bytes) -> None:
        """Add XMP metadata to an image. The data should be XMP XML as bytes."""

    def add_generic_metadata(
        self,
        handle: HeifImageHandle,
        data: bytes,
        item_type: str,
        content_type: str = "",
    ) -> None:
        """
        Add generic metadata to an image with specified item type and optional content type.
        """

    def __enter__(self) -> HeifContext: ...
    def __exit__(self, *args) -> None: ...

class HeifImageHandle:
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def has_alpha(self) -> bool: ...
    @property
    def luma_bits_per_pixel(self) -> int: ...
    @property
    def chroma_bits_per_pixel(self) -> int: ...
    def decode(
        self,
        colorspace: HeifColorspace = HeifColorspace.RGB,
        chroma: HeifChroma = HeifChroma.InterleavedRGB,
        options: HeifDecodingOptions | None = None,
    ) -> HeifImage: ...
    def get_metadata_block_ids(self, type_filter: str = "") -> list[int]: ...
    def get_metadata_block_type(self, arg: int, /) -> str: ...
    def get_metadata_block(self, arg: int, /) -> bytes: ...
    def get_auxiliary_image_ids(self, aux_key_mask: int = 0) -> list[int]: ...
    def get_auxiliary_type(self) -> str: ...
    def get_auxiliary_image_handle(self, id: int, /) -> HeifImageHandle: ...
    @property
    def color_profile_type(self) -> HeifColorProfileType: ...
    def get_raw_color_profile(self) -> bytes: ...
    def get_nclx_color_profile(self) -> HeifColorProfileNclx | None: ...
    @property
    def has_content_light_level(self) -> bool: ...
    @property
    def has_mastering_display_colour_volume(self) -> bool: ...
    @property
    def has_ambient_viewing_environment(self) -> bool: ...
    @property
    def content_light_level(self) -> HeifContentLightLevel | None: ...
    @property
    def mastering_display_colour_volume(
        self,
    ) -> HeifMasteringDisplayColourVolume | None: ...
    @property
    def ambient_viewing_environment(self) -> HeifAmbientViewingEnvironment | None: ...

class HeifImage:
    def __init__(
        self, arg0: int, arg1: int, arg2: HeifColorspace, arg3: HeifChroma, /
    ) -> None: ...
    @staticmethod
    def from_numpy(arr: numpy.ndarray, bit_depth: int = 10) -> HeifImage: ...
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    def get_width(self, arg: HeifChannel, /) -> int: ...
    def get_height(self, arg: HeifChannel, /) -> int: ...
    def add_plane(
        self, arg0: HeifChannel, arg1: int, arg2: int, arg3: int, /
    ) -> None: ...
    def get_plane(
        self, channel: HeifChannel, writeable: bool = False
    ) -> numpy.ndarray: ...
    @property
    def color_profile_type(self) -> HeifColorProfileType: ...
    def get_raw_color_profile(self) -> bytes: ...
    def get_nclx_color_profile(self) -> HeifColorProfileNclx | None: ...
    def set_raw_color_profile(self, profile_type: str, data: bytes, /) -> None: ...
    def set_nclx_color_profile(
        self, color_profile: HeifColorProfileNclx, /
    ) -> None: ...
    @property
    def has_content_light_level(self) -> bool: ...
    @property
    def has_mastering_display_colour_volume(self) -> bool: ...
    @property
    def has_ambient_viewing_environment(self) -> bool: ...
    @property
    def content_light_level(self) -> HeifContentLightLevel | None: ...
    @content_light_level.setter
    def content_light_level(self, value: HeifContentLightLevel) -> None: ...
    @property
    def mastering_display_colour_volume(
        self,
    ) -> HeifMasteringDisplayColourVolume | None: ...
    @mastering_display_colour_volume.setter
    def mastering_display_colour_volume(
        self, value: HeifMasteringDisplayColourVolume
    ) -> None: ...
    @property
    def ambient_viewing_environment(self) -> HeifAmbientViewingEnvironment | None: ...
    @ambient_viewing_environment.setter
    def ambient_viewing_environment(
        self, value: HeifAmbientViewingEnvironment
    ) -> None: ...

class HeifPlaneLayout:
    channel: HeifChannel
    width: int
    height: int
    stride_bytes: int
    num_channels: int
    bits_per_pixel: int
    bytes_per_channel: int
    is_big_endian: bool
    def shape(self) -> list[int]: ...
    def strides(self) -> list[int]: ...

class HeifImageLayout:
    @staticmethod
    def from_image(img: HeifImage) -> HeifImageLayout: ...
    def get_plane_layout(
        self, channel: HeifChannel, stride_bytes: int, bits_per_pixel: int
    ) -> HeifPlaneLayout: ...
    @property
    def colorspace(self) -> HeifColorspace: ...
    @property
    def chroma(self) -> HeifChroma: ...
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...

class HeifEncoderDescriptor:
    @property
    def id_name(self) -> str: ...
    @property
    def name(self) -> str: ...
    @property
    def compression_format(self) -> HeifCompressionFormat: ...

def get_encoder_descriptors(
    format_filter: HeifCompressionFormat = HeifCompressionFormat.Undefined,
    name_filter: str = "",
) -> list[HeifEncoderDescriptor]: ...

class HeifEncoderParameterType(enum.Enum):
    Integer = 1
    Boolean = 2
    String = 3

class HeifEncoderParameter:
    @property
    def name(self) -> str: ...
    @property
    def type(self) -> HeifEncoderParameterType: ...
    @property
    def has_default(self) -> bool: ...
    @property
    def default_value(self) -> int | bool | str | None: ...
    @property
    def valid_integer_range(self) -> tuple[int, int] | None: ...
    @property
    def valid_integer_values(self) -> list[int] | None: ...
    @property
    def valid_string_values(self) -> list[str] | None: ...

class HeifEncoder:
    @overload
    def __init__(self, arg: HeifCompressionFormat, /) -> None: ...
    @property
    def parameters(self) -> HeifEncoderParametersProxy: ...
    @overload
    def __init__(self, arg: HeifEncoderDescriptor, /) -> None: ...
    @property
    def name(self) -> str: ...
    def set_lossy_quality(self, arg: int, /) -> None: ...
    def set_lossless(self, arg: bool, /) -> None: ...
    def set_parameter(self, arg0: str, arg1: str, /) -> None: ...
    def get_parameter(self, name: str, /) -> str: ...
    def set_integer_parameter(self, name: str, value: int, /) -> None: ...
    def get_integer_parameter(self, name: str, /) -> int: ...
    def set_boolean_parameter(self, name: str, value: bool, /) -> None: ...
    def get_boolean_parameter(self, name: str, /) -> bool: ...
    def set_string_parameter(self, name: str, value: str, /) -> None: ...
    def get_string_parameter(self, name: str, /) -> str: ...
    def _list_parameters(self) -> list[HeifEncoderParameter]: ...
    def encode_image(
        self,
        ctx: HeifContext,
        image: HeifImage,
        preset: str = "",
        options: HeifEncodingOptions | None = None,
    ) -> HeifImageHandle: ...

AUX_IMAGE_FILTER_OMIT_ALPHA: int
AUX_IMAGE_FILTER_OMIT_DEPTH: int
