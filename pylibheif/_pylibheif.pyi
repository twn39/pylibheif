"""Python bindings for libheif using nanobind"""

import enum
import numpy
from typing import overload

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

C420: HeifChroma = HeifChroma.C420

C422: HeifChroma = HeifChroma.C422

C444: HeifChroma = HeifChroma.C444

InterleavedRGB: HeifChroma = HeifChroma.InterleavedRGB

InterleavedRGBA: HeifChroma = HeifChroma.InterleavedRGBA

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

class HeifError(Exception):
    pass

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
    ) -> HeifImage: ...
    def get_metadata_block_ids(self, type_filter: str = "") -> list[int]: ...
    def get_metadata_block_type(self, arg: int, /) -> str: ...
    def get_metadata_block(self, arg: int, /) -> bytes: ...

class HeifImage:
    def __init__(
        self, arg0: int, arg1: int, arg2: HeifColorspace, arg3: HeifChroma, /
    ) -> None: ...
    @staticmethod
    def from_numpy(arr: numpy.ndarray) -> HeifImage: ...
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

class HeifEncoder:
    @overload
    def __init__(self, arg: HeifCompressionFormat, /) -> None: ...
    @overload
    def __init__(self, arg: HeifEncoderDescriptor, /) -> None: ...
    @property
    def name(self) -> str: ...
    def set_lossy_quality(self, arg: int, /) -> None: ...
    def set_parameter(self, arg0: str, arg1: str, /) -> None: ...
    def encode_image(
        self, ctx: HeifContext, image: HeifImage, preset: str = ""
    ) -> HeifImageHandle: ...
