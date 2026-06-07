# pylibheif

[![PyPI version](https://badge.fury.io/py/pylibheif.svg)](https://badge.fury.io/py/pylibheif)
[![Build and Publish](https://github.com/twn39/pylibheif/actions/workflows/build.yml/badge.svg)](https://github.com/twn39/pylibheif/actions/workflows/build.yml)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Python bindings for [libheif](https://github.com/strukturag/libheif) using nanobind.

## Features

- **HEIC/HEIF Support**: Read and write HEIC images (HEVC/H.265 encoded)
- **AVIF Support**: Read and write AVIF images (AV1 encoded)
- **JPEG2000 Support**: Read and write JPEG2000 images in HEIF container
- **NumPy Integration**: Zero-copy access to image data via Python Buffer Protocol
- **Metadata Support**: Read and write EXIF, XMP, and custom metadata
- **HDR Metadata Support**: Read and write HDR metadata (CLLI, MDCV, AMVE) using physical units (Nits, Lux, CIE coordinates) with type safety
- **Asynchronous Support**: Built-in `asyncio` wrappers for non-blocking I/O and encoding
- **RAII Resource Management**: Automatic resource cleanup with context managers

## Supported Formats

| Format | Decoding | Encoding | Codec |
|--------|----------|----------|-------|
| HEIC (HEVC/H.265) | ✅ | ✅ | libde265 (Dec) / x265 (Enc) / Kvazaar (Enc) |
| AVIF (AV1) | ✅ | ✅ | DAV1D (Dec) / AOM (Enc) |
| JPEG2000 | ✅ | ✅ | OpenJPEG |
| JPEG | ✅ | ✅ | libjpeg |

## Requirements

- Python >= 3.11
- NumPy >= 1.26.0
- CMake >= 3.15
- C++17 compatible compiler

## Installation

```bash
pip install pylibheif
```

Or with uv:
```bash
uv pip install pylibheif
```

### Building from Source

```bash
# Clone with submodules
git clone --recursive https://github.com/twn39/pylibheif.git
cd pylibheif

# Install
uv pip install -e .
```

## Usage

### Reading HEIC/AVIF Images

**Using context manager (recommended):**

```python
import pylibheif
import numpy as np

# Open HEIC file with context manager
with pylibheif.HeifContext() as ctx:
    ctx.read_from_file('image.heic')
    
    # Get primary image handle
    handle = ctx.get_primary_image_handle()
    print(f'Image size: {handle.width}x{handle.height}')
    print(f'Has alpha: {handle.has_alpha}')
    
    # Decode to RGB
    img = handle.decode(pylibheif.HeifColorspace.RGB, 
                        pylibheif.HeifChroma.InterleavedRGB)
    
    # Get as NumPy array (zero-copy)
    arr = img.get_plane(pylibheif.HeifChannel.Interleaved, False)  # shape: (height, width, 3)
```

**Explicit creation (for more control):**

```python
import pylibheif
import numpy as np

# Create context explicitly
ctx = pylibheif.HeifContext()
ctx.read_from_file('image.heic')

handle = ctx.get_primary_image_handle()
img = handle.decode(pylibheif.HeifColorspace.RGB, 
                    pylibheif.HeifChroma.InterleavedRGB)
arr = img.get_plane(pylibheif.HeifChannel.Interleaved, False)

# Resources are automatically freed when objects go out of scope
```

### Writing HEIC Images (H.265)

```python
import pylibheif
import numpy as np

# Create image from NumPy array
width, height = 1920, 1080
img = pylibheif.HeifImage(width, height, 
                          pylibheif.HeifColorspace.RGB,
                          pylibheif.HeifChroma.InterleavedRGB)
img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

# Fill with data
arr = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
arr[:] = your_image_data  # your RGB data

# Encode and save as HEIC
ctx = pylibheif.HeifContext()
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
encoder.set_lossy_quality(85)
encoder.encode_image(ctx, img)

ctx.write_to_file('output.heic')
```

### Writing AVIF Images (AV1)

```python
import pylibheif
import numpy as np

# Prepare image (same as above)
width, height = 1920, 1080
img = pylibheif.HeifImage(width, height, 
                          pylibheif.HeifColorspace.RGB,
                          pylibheif.HeifChroma.InterleavedRGB)
img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

# Encode and save as AVIF
ctx = pylibheif.HeifContext()

# Use AV1 format for AVIF
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.AV1)
encoder.set_lossy_quality(85)
encoder.set_parameter("speed", "6") # Optional: Tune speed (0-9)

encoder.encode_image(ctx, img)

# Save with .avif extension
ctx.write_to_file('output.avif')
```

### Writing JPEG Images

```python
import pylibheif
import numpy as np

# Prepare image (same as above)
width, height = 1920, 1080
img = pylibheif.HeifImage(width, height, 
                          pylibheif.HeifColorspace.RGB,
                          pylibheif.HeifChroma.InterleavedRGB)
img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

# Encode and save as JPEG
ctx = pylibheif.HeifContext()

# Use JPEG format
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.JPEG)
encoder.set_lossy_quality(90) # Quality 0-100

encoder.encode_image(ctx, img)

# Save with .jpg extension
ctx.write_to_file('output.jpg')
```

### Writing JPEG2000 Images

```python
import pylibheif
import numpy as np

# Prepare image (same as above)
width, height = 1920, 1080
img = pylibheif.HeifImage(width, height, 
                          pylibheif.HeifColorspace.RGB,
                          pylibheif.HeifChroma.InterleavedRGB)
img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

# Encode and save as JPEG2000 in HEIF container
ctx = pylibheif.HeifContext()

# Use JPEG2000 format
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.JPEG2000)
encoder.set_lossy_quality(85) # Quality 0-100

encoder.encode_image(ctx, img)

# Save with .jp2 or .heif extension
# Note: libheif typically saves JPEG2000 in a HEIF container
ctx.write_to_file('output.heif')
```

### Encoder Selection

By default, `pylibheif` selects the best available encoder for the requested format (e.g. x265 for HEVC). You can also explicitly select a specific encoder (e.g. Kvazaar) if available.

```python
import pylibheif

# 1. Get all available HEVC encoders
descriptors = pylibheif.get_encoder_descriptors(pylibheif.HeifCompressionFormat.HEVC)

# Print available encoders
for d in descriptors:
    print(f"ID: {d.id_name}, Name: {d.name}")

# 2. Find specific encoder (e.g. Kvazaar)
kvazaar_desc = next((d for d in descriptors if "kvazaar" in d.id_name), None)

if kvazaar_desc:
    # 3. Create encoder explicitly using the descriptor
    encoder = pylibheif.HeifEncoder(kvazaar_desc)
    
    # Verify which encoder is used
    print(f"Using encoder: {encoder.name}")
    
    encoder.set_lossy_quality(85)
    # encoder.encode_image(...)
    # encoder.encode_image(...)
```

### Reading Metadata

```python
import pylibheif

ctx = pylibheif.HeifContext()
ctx.read_from_file('image.heic')
handle = ctx.get_primary_image_handle()

# Get metadata block IDs
exif_ids = handle.get_metadata_block_ids('Exif')
for id in exif_ids:
    metadata_type = handle.get_metadata_block_type(id)
    metadata_bytes = handle.get_metadata_block(id)
    print(f'Metadata type: {metadata_type}, size: {len(metadata_bytes)}')
```

### Writing Metadata

```python
import pylibheif
import numpy as np

# Create and encode an image
width, height = 64, 64
img = pylibheif.HeifImage(width, height,
                          pylibheif.HeifColorspace.RGB,
                          pylibheif.HeifChroma.InterleavedRGB)
img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
arr = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
arr[:] = 128  # fill with gray

ctx = pylibheif.HeifContext()
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
encoder.set_lossy_quality(85)
handle = encoder.encode_image(ctx, img)

# Add EXIF metadata (with 4-byte offset prefix for TIFF header)
exif_data = b'\x00\x00\x00\x00' + b'Exif\x00\x00' + b'II*\x00...'  # your EXIF data
ctx.add_exif_metadata(handle, exif_data)

# Add XMP metadata
xmp_data = b'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:creator>My App</dc:creator>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''
ctx.add_xmp_metadata(handle, xmp_data)

# Add custom/generic metadata
custom_data = b'{"app": "myapp", "version": "1.0"}'
ctx.add_generic_metadata(handle, custom_data, "json", "application/json")

# Save
ctx.write_to_file('output_with_metadata.heic')
```

### HDR Metadata

`pylibheif` supports reading and writing standard HDR metadata introduced in `libheif 1.23.0`:
- **Content Light Level (CLLI)**: MaxCLL (Max Content Light Level) and MaxFALL (Max Frame Average Light Level) in nits.
- **Mastering Display Colour Volume (MDCV)**: Mastering display primaries (Red, Green, Blue, White point) in CIE xy coordinates, and luminance range in nits.
- **Ambient Viewing Environment (AMVE)**: Ambient illumination in lux, and ambient light CIE xy coordinates.

The API exposes these values using standard float coordinates and physical units. It automatically handles the underlying fixed-point scaling and Annex E array index mapping (e.g. green-blue-red ordering in MDCV).

#### Reading HDR Metadata

You can query and retrieve HDR metadata from `HeifImageHandle` (or `AsyncHeifImageHandle`):

```python
import pylibheif

with pylibheif.HeifContext() as ctx:
    ctx.read_from_file('hdr_image.heic')
    handle = ctx.get_primary_image_handle()
    
    # 1. Content Light Level (CLLI)
    if handle.has_content_light_level:
        cll = handle.content_light_level
        print(f"MaxCLL: {cll.max_content_light_level} nits")
        print(f"MaxFALL: {cll.max_pic_average_light_level} nits")
        
    # 2. Mastering Display Colour Volume (MDCV)
    if handle.has_mastering_display_colour_volume:
        mdcv = handle.mastering_display_colour_volume
        print(f"Red Primary: {mdcv.red_primary}")        # e.g., (0.680, 0.320)
        print(f"Green Primary: {mdcv.green_primary}")    # e.g., (0.265, 0.690)
        print(f"Blue Primary: {mdcv.blue_primary}")      # e.g., (0.150, 0.060)
        print(f"White Point: {mdcv.white_point}")        # e.g., (0.3127, 0.3290)
        print(f"Luminance Range: {mdcv.min_luminance} to {mdcv.max_luminance} nits")
        
    # 3. Ambient Viewing Environment (AMVE)
    if handle.has_ambient_viewing_environment:
        amve = handle.ambient_viewing_environment
        print(f"Ambient Illumination: {amve.ambient_illumination} lux")
        print(f"Ambient Light: {amve.ambient_light}")
```

#### Writing HDR Metadata

You can attach HDR metadata to `HeifImage` prior to encoding:

```python
import pylibheif
import numpy as np

# Prepare image
img = pylibheif.HeifImage(64, 64, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB)
img.add_plane(pylibheif.HeifChannel.Interleaved, 64, 64, 8)
arr = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
arr[:] = 128  # Fill with gray

# 1. Set CLLI
img.content_light_level = pylibheif.HeifContentLightLevel(
    max_content_light_level=1000,
    max_pic_average_light_level=400
)

# 2. Set MDCV (mastering display characteristics)
img.mastering_display_colour_volume = pylibheif.HeifMasteringDisplayColourVolume(
    red_primary=(0.680, 0.320),
    green_primary=(0.265, 0.690),
    blue_primary=(0.150, 0.060),
    white_point=(0.3127, 0.3290),
    max_luminance=1000.0,
    min_luminance=0.005
)

# 3. Set AMVE
img.ambient_viewing_environment = pylibheif.HeifAmbientViewingEnvironment(
    ambient_illumination=315.5,
    ambient_light=(0.3127, 0.3290)
)

# Encode
ctx = pylibheif.HeifContext()
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
encoder.encode_image(ctx, img)
ctx.write_to_file('hdr_output.heic')
```

### Asynchronous Support (asyncio)

`pylibheif` provides asynchronous wrappers for non-blocking I/O and CPU-intensive operations (like encoding and decoding) using `asyncio.to_thread`.

#### Async Reading and Decoding

```python
import pylibheif
import asyncio
import numpy as np

async def read_async():
    # Recommended: Use 'async with' context manager
    async with pylibheif.AsyncHeifContext() as ctx:
        await ctx.read_from_file('image.heic')
        
        handle = ctx.get_primary_image_handle()
        
        # Asynchronously decode (offloaded to thread)
        img = await handle.decode(pylibheif.HeifColorspace.RGB, 
                                  pylibheif.HeifChroma.InterleavedRGB)
        
        arr = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
        return arr

asyncio.run(read_async())
```

#### Async Encoding and Writing

```python
import pylibheif
import asyncio
import numpy as np

async def write_async(image_data):
    width, height = 1920, 1080
    img = pylibheif.HeifImage(width, height, 
                              pylibheif.HeifColorspace.RGB,
                              pylibheif.HeifChroma.InterleavedRGB)
    img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    arr = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    arr[:] = image_data

    async with pylibheif.AsyncHeifContext() as ctx:
        encoder = pylibheif.AsyncHeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(85)
        
        # Asynchronously encode (offloaded to thread)
        await encoder.encode_image(ctx, img)
        
        # Asynchronously write to file
        await ctx.write_to_file('output.heic')

asyncio.run(write_async(your_image_data))
```

## API Reference

### class `pylibheif.HeifContext`

Manages the valid lifetime of libheif context. It is the main entry point (root object) for high-level API.

#### Methods

**`__init__()`**
Creates a new empty context.

**`read_from_file(filename: str) -> None`**
Reads a HEIF file from the given filename.
- `filename`: Path to the HEIF file.

**`read_from_memory(data: bytes) -> None`**
Reads a HEIF file from a bytes object.
- `data`: Bytes containing the file content.

**`write_to_file(filename: str) -> None`**
Writes the current context to a file.
- `filename`: Destination path.

**`write_to_bytes() -> bytes`**
Writes the current context to a bytes object.
- Returns: `bytes` object containing the encoded file data.

**`get_primary_image_handle() -> HeifImageHandle`**
Gets the handle for the primary image in the file.
- Returns: `HeifImageHandle` for the primary image.

**`get_image_handle(id: int) -> HeifImageHandle`**
Gets the handle for a specific image ID.
- `id`: The ID of the image (see `get_list_of_top_level_image_IDs`).
- Returns: `HeifImageHandle`.

**`get_list_of_top_level_image_IDs() -> List[int]`**
Gets a list of IDs of all top-level images in the file.
- Returns: List of integer IDs.

**`add_exif_metadata(handle: HeifImageHandle, data: bytes) -> None`**
Adds EXIF metadata to the specified image.
- `handle`: Image handle from encoding.
- `data`: Raw EXIF bytes (with 4-byte offset prefix for TIFF header).

**`add_xmp_metadata(handle: HeifImageHandle, data: bytes) -> None`**
Adds XMP metadata to the specified image.
- `handle`: Image handle from encoding.
- `data`: XMP XML as bytes.

**`add_generic_metadata(handle: HeifImageHandle, data: bytes, item_type: str, content_type: str = "") -> None`**
Adds generic/custom metadata to the specified image.
- `handle`: Image handle from encoding.
- `data`: Raw metadata bytes.
- `item_type`: Metadata item type (e.g. "json", "iptc").
- `content_type`: Optional MIME content type (e.g. "application/json").

---

### class `pylibheif.HeifImageHandle`

Represents a compressed image within the HEIF file.

#### Properties

- **`width`** *(int)*: The width of the image.
- **`height`** *(int)*: The height of the image.
- **`has_alpha`** *(bool)*: True if the image has an alpha channel.
- **`has_content_light_level`** *(bool)*: True if CLLI metadata is present.
- **`has_mastering_display_colour_volume`** *(bool)*: True if MDCV metadata is present.
- **`has_ambient_viewing_environment`** *(bool)*: True if AMVE metadata is present.
- **`content_light_level`** *(Optional[HeifContentLightLevel])*: CLLI metadata if present, otherwise `None`.
- **`mastering_display_colour_volume`** *(Optional[HeifMasteringDisplayColourVolume])*: MDCV metadata if present, otherwise `None`.
- **`ambient_viewing_environment`** *(Optional[HeifAmbientViewingEnvironment])*: AMVE metadata if present, otherwise `None`.

#### Methods

**`decode(colorspace: HeifColorspace = HeifColorspace.RGB, chroma: HeifChroma = HeifChroma.InterleavedRGB) -> HeifImage`**
Decodes the image handle into an uncompressed `HeifImage`.
- `colorspace`: Target colorspace (default: RGB).
- `chroma`: Target chroma format (default: InterleavedRGB).
- Returns: Decoded `HeifImage`.

**`get_metadata_block_ids(type_filter: str = "") -> List[str]`**
Gets a list of metadata block IDs attached to this image.
- `type_filter`: Optional filter string (e.g. "Exif", "XMP").
- Returns: List of metadata ID strings.

**`get_metadata_block_type(id: str) -> str`**
Gets the type string of a specific metadata block.
- `id`: Metadata ID.
- Returns: Type string (e.g. "Exif").

**`get_metadata_block(id: str) -> bytes`**
Gets the raw data of a metadata block.
- `id`: Metadata ID.
- Returns: `bytes` object containing the metadata.

---

### class `pylibheif.HeifImage`

Represents an uncompressed image containing pixel data. Supports zero-copy memory access via nanobind's ndarray integration.

#### Properties

- **`width`** *(int)*: The width of the image.
- **`height`** *(int)*: The height of the image.
- **`has_content_light_level`** *(bool)*: True if CLLI metadata is present.
- **`has_mastering_display_colour_volume`** *(bool)*: True if MDCV metadata is present.
- **`has_ambient_viewing_environment`** *(bool)*: True if AMVE metadata is present.
- **`content_light_level`** *(Optional[HeifContentLightLevel])*: Get or set CLLI metadata.
- **`mastering_display_colour_volume`** *(Optional[HeifMasteringDisplayColourVolume])*: Get or set MDCV metadata.
- **`ambient_viewing_environment`** *(Optional[HeifAmbientViewingEnvironment])*: Get or set AMVE metadata.

#### Methods

**`__init__(width: int, height: int, colorspace: HeifColorspace, chroma: HeifChroma)`**
Creates a new empty image.
- `width`: Image width.
- `height`: Image height.
- `colorspace`: Image colorspace.
- `chroma`: Image chroma format.

**`add_plane(channel: HeifChannel, width: int, height: int, bit_depth: int) -> None`**
Adds a new plane to the image.
- `channel`: The channel type (e.g. `HeifChannel.Interleaved`).
- `width`: Width of the plane.
- `height`: Height of the plane.
- `bit_depth`: Bit depth (e.g. 8).

**`get_plane(channel: HeifChannel, writeable: bool = False) -> np.ndarray`**
Gets a zero-copy NumPy array mapping to the image plane memory.
- `channel`: The channel to retrieve.
- `writeable`: Whether the buffer should be writable.
- Returns: `numpy.ndarray` mapped to the underlying `libheif` memory.

---

### class `pylibheif.HeifEncoder`

Controls the encoding process.

#### Methods

**`__init__(format: HeifCompressionFormat)`**
Creates a new encoder for the specified format.
- `format`: Compression format (e.g. `HeifCompressionFormat.HEVC`).

**`set_lossy_quality(quality: int) -> None`**
Sets the quality for lossy compression.
- `quality`: Integer between 0 (lowest) and 100 (highest).

**`set_parameter(name: str, value: str) -> None`**
Sets a low-level encoder parameter.
- `name`: Parameter name (e.g. "speed" for AV1).
- `value`: Parameter value.

**`encode_image(context: HeifContext, image: HeifImage, preset: str = "") -> HeifImageHandle`**
Encodes the given image and appends it to the context.
- `context`: The destination `HeifContext`.
- `image`: The source `HeifImage` to encode.
- `preset`: Optional encoder preset (e.g. "ultrafast", "slow"). Default is empty (balanced/default). **Note**: This maps to the 'preset' parameter in libheif. It works for x265 (check version), but AOM and others may use different parameters (e.g. 'speed') which should be set via `set_parameter` instead.
- Returns: `HeifImageHandle` for the encoded image. Can be used to add metadata.

---

### HDR Metadata Classes

#### class `pylibheif.HeifContentLightLevel`

Holds Content Light Level Information (CLLI) as integers.

- **`max_content_light_level`** *(int)*: Maximum content light level (MaxCLL) in nits.
- **`max_pic_average_light_level`** *(int)*: Maximum picture average light level (MaxFALL) in nits.

#### class `pylibheif.HeifMasteringDisplayColourVolume`

Holds Mastering Display Colour Volume (MDCV) metadata. All coordinates are normalized CIE 1931 xy floating-point coordinates.

- **`red_primary`** *(Tuple[float, float])*: Chromaticity coordinates (x, y) of the red primary.
- **`green_primary`** *(Tuple[float, float])*: Chromaticity coordinates (x, y) of the green primary.
- **`blue_primary`** *(Tuple[float, float])*: Chromaticity coordinates (x, y) of the blue primary.
- **`white_point`** *(Tuple[float, float])*: Chromaticity coordinates (x, y) of the white point.
- **`max_luminance`** *(float)*: Maximum display mastering luminance in nits.
- **`min_luminance`** *(float)*: Minimum display mastering luminance in nits.

#### class `pylibheif.HeifAmbientViewingEnvironment`

Holds Ambient Viewing Environment (AMVE) metadata.

- **`ambient_illumination`** *(float)*: Ambient illumination in lux.
- **`ambient_light`** *(Tuple[float, float])*: Chromaticity coordinates (x, y) of the ambient light.

---

### class `pylibheif.AsyncHeifContext`

Asynchronous wrapper for `HeifContext`. Methods are awaited and offloaded to a background thread.

#### Methods

**`async read_from_file(filename: str) -> None`**
**`async read_from_memory(data: bytes) -> None`**
**`async write_to_file(filename: str) -> None`**
**`async write_to_bytes() -> bytes`**
**`get_primary_image_handle() -> AsyncHeifImageHandle`**
**`get_image_handle(id: int) -> AsyncHeifImageHandle`**

---

### class `pylibheif.AsyncHeifImageHandle`

Asynchronous wrapper for `HeifImageHandle`.

#### Methods

**`async decode(colorspace, chroma) -> HeifImage`**
Asynchronously decodes the image.

---

### class `pylibheif.AsyncHeifEncoder`

Asynchronous wrapper for `HeifEncoder`.

#### Methods

**`async encode_image(ctx, image, preset="") -> HeifImageHandle`**
Asynchronously encodes the image.

---

### Enums

#### `pylibheif.HeifColorspace`
- `RGB`, `YCbCr`, `Monochrome`, `Undefined`

#### `pylibheif.HeifChroma`
- `InterleavedRGB`: Interleaved R, G, B bytes.
- `InterleavedRGBA`: Interleaved R, G, B, A bytes.
- `C420`: YUV 4:2:0 planar.
- `C422`: YUV 4:2:2 planar.
- `C444`: YUV 4:4:4 planar.
- `Monochrome`.

#### `pylibheif.HeifChannel`
- `Interleaved`: For interleaved RGB/RGBA.
- `Y`, `Cb`, `Cr`: For YUV planar.
- `R`, `G`, `B`: For RGB planar.
- `Alpha`: For Alpha channel.

#### `pylibheif.HeifCompressionFormat`
- `HEVC`: H.265 (libx265).
- `AV1`: AV1 (AOM/RAV1E/SVT).
- `JPEG`: JPEG.
- `JPEG2000`: JPEG 2000 (OpenJPEG).

## Building from Source

```bash
# Clone with submodules
git clone --recursive https://github.com/your-username/pylibheif.git
cd pylibheif

# Build
uv pip install -e .
```

## Performance

Benchmarks on 1920x1080 (HD) RGB real-world images (Apple Silicon), comparing python libraries.

| Operation | Library / Encoder | Mean Time |
|:---|:---|:---:|
| **Decoding** | `pillow-heif` | ~60.5 ms |
| **Decoding** | `pylibheif` (HEVC) | ~71.3 ms |
| **Encoding** | `pylibheif` / Kvazaar | ~174.4 ms |
| **Encoding** | `pillow-heif` / x265 | ~247.3 ms |
| **Encoding** | `pylibheif` / x265 (Q80) | ~255.7 ms |
| **Encoding** | `pylibheif` / AV1 (AOM) | ~292.4 ms |

### Key Findings:

1.  **Decoding Parity**: `pylibheif` natively fetching Python 0-copy numpy arrays from underlying native libheif decoders delivers heavily competitive and fast decode speeds within 10ms of specially tuned PIL alternatives.
2.  **HEVC Performance**: The `kvazaar` encoder significantly outperforms the default fallback `x265` options available in other packages while retaining identical interfaces.
3.  **Versatility**: `pylibheif` brings near-realtime AV1 encoding capabilities reliably into Python ecosystem bounds without falling apart gracefully scaling AV1 complexity.

<details>
<summary><b>Raw Benchmark Output (Apple M Series)</b></summary>

```text
-----------------------------------------------------------------------------------------------------------------------------------
Name (time in ms)                          Mean            OPS
-----------------------------------------------------------------------------------------------------------------------------------
test_benchmark_decode_hevc_pillow         60.56          16.49  (pillow-heif)
test_benchmark_decode_hevc                71.34          14.01  (pylibheif direct)
test_benchmark_encode_kvazaar            174.47           5.73  (pylibheif, kvazaar, Q80)
test_benchmark_encode_hevc_pillow        247.33           4.04  (pillow-heif, x265, Q80)
test_benchmark_encode_hevc               255.72           3.91  (pylibheif, x265, Q80)
test_benchmark_encode_av1                292.44           3.41  (pylibheif, aom, speed=6)
-----------------------------------------------------------------------------------------------------------------------------------
```

</details>

Run benchmarks yourself:
```bash
uv pip install pillow-heif pytest-benchmark
uv run pytest tests/test_benchmark.py --benchmark-only --benchmark-min-rounds=20
```

## License

This project is licensed under the LGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [libheif](https://github.com/strukturag/libheif) - HEIF/AVIF codec library
- [nanobind](https://nanobind.readthedocs.io) - Modern C++/Python bindings
