# pylibheif

[![PyPI version](https://badge.fury.io/py/pylibheif.svg)](https://badge.fury.io/py/pylibheif)
[![Build and Publish](https://github.com/twn39/pylibheif/actions/workflows/build.yml/badge.svg)](https://github.com/twn39/pylibheif/actions/workflows/build.yml)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Python bindings for [libheif](https://github.com/strukturag/libheif) using pybind11.

## Features

- **HEIC/HEIF Support**: Read and write HEIC images (HEVC/H.265 encoded)
- **AVIF Support**: Read and write AVIF images (AV1 encoded)
- **JPEG2000 Support**: Read and write JPEG2000 images in HEIF container
- **NumPy Integration**: Zero-copy access to image data via Python Buffer Protocol
- **Metadata Support**: Read and write EXIF, XMP, and custom metadata
- **RAII Resource Management**: Automatic resource cleanup with context managers

## Supported Formats

| Format | Decoding | Encoding | Codec |
|--------|----------|----------|-------|
| HEIC (HEVC/H.265) | ✅ | ✅ | libde265 / x265 |
| AVIF (AV1) | ✅ | ✅ | DAV1D + AOM |
| JPEG2000 | ✅ | ✅ | OpenJPEG |

## Requirements

- Python >= 3.12
- NumPy >= 1.26.0
- CMake >= 3.15
- C++17 compatible compiler

### System Dependencies

```bash
# macOS
brew install openjpeg

# Ubuntu/Debian
sudo apt install libopenjp2-7-dev
```

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
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
    arr = np.asarray(plane)  # shape: (height, width, 3)
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
plane = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
arr = np.asarray(plane)

# Resources are automatically freed when objects go out of scope
```

### Writing HEIC/AVIF Images

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
plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
arr = np.asarray(plane)
arr[:] = your_image_data  # your RGB data

# Encode and save
ctx = pylibheif.HeifContext()

# For HEIC (HEVC)
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
# For AVIF (AV1)
# encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.AV1)
# For JPEG2000
# encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.JPEG2000)

encoder.set_lossy_quality(85)
encoder.encode_image(ctx, img)
ctx.write_to_file('output.heic')
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
```

### Converting HEIC to JPEG

```python
import pylibheif
import numpy as np
from PIL import Image

# Decode HEIC
ctx = pylibheif.HeifContext()
ctx.read_from_file('input.heic')
handle = ctx.get_primary_image_handle()
img = handle.decode(pylibheif.HeifColorspace.RGB, 
                    pylibheif.HeifChroma.InterleavedRGB)

# Get NumPy array
plane = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
arr = np.asarray(plane)

# Save as JPEG using PIL
pil_img = Image.fromarray(arr)
pil_img.save('output.jpg', 'JPEG', quality=85)
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
plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
arr = np.asarray(plane)
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

Represents an uncompressed image containing pixel data. Supports the Python Buffer Protocol for zero-copy access with NumPy.

#### Properties

- **`width`** *(int)*: The width of the image.
- **`height`** *(int)*: The height of the image.

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

**`get_plane(channel: HeifChannel, writeable: bool = False) -> HeifPlane`**
Gets a plane object that supports the buffer protocol.
- `channel`: The channel to retrieve.
- `writeable`: Whether the buffer should be writable.
- Returns: `HeifPlane` object (wrappable with `np.asarray()`).

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

**`encode_image(context: HeifContext, image: HeifImage) -> HeifImageHandle`**
Encodes the given image and appends it to the context.
- `context`: The destination `HeifContext`.
- `image`: The source `HeifImage` to encode.
- Returns: `HeifImageHandle` for the encoded image. Can be used to add metadata.

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

Benchmarks on 1920x1080 RGB image (Apple Silicon):

| Operation | pylibheif | pillow-heif | Note |
|:---|:---:|:---:|:---|
| HEVC Decode | 31 ms | 26 ms | |
| HEVC Encode (x265) | 282 ms | 303 ms | Quality 80 |
| HEVC Encode (Kvazaar) | 136 ms | - | Quality 80 |
| AV1 Encode | 97 ms | - | Quality 80* |

### Key Benchmark Findings (based on 20-round test):

1.  **Kvazaar Speed & Stability**: Kvazaar demonstrates a solid **~2x speed advantage** over x265 (default settings) at the same quality level. Furthermore, it is extremely stable with a standard deviation of only **1.1ms**, compared to **23ms** for x265.
2.  **AV1 Performance**: In our tests, the AOM AV1 encoder was surprisingly fast. This is due to its default `speed` parameter being set to **6**, which is an aggressive performance preset.
3.  **Efficiency**: `pylibheif` provides significant performance benefits for heavy encoding workloads where encoder selection and fine-tuning are critical.

<details>
<summary><b>Raw Benchmark Output (Refined 20-round run)</b></summary>

```text
-------------------------------------------------------------------------------------------- benchmark: 6 tests -------------------------------------------------------------------------------------------
Name (time in ms)                          Min                 Max                Mean             StdDev              Median                IQR            Outliers      OPS            Rounds  Iterations
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
test_benchmark_decode_hevc_pillow      24.8845 (1.0)       26.6724 (1.0)       25.5582 (1.0)       0.4550 (1.0)       25.4610 (1.0)       0.5293 (1.20)          9;2  39.1264 (1.0)          34           1
test_benchmark_decode_hevc             30.4714 (1.22)      32.3889 (1.21)      31.2734 (1.22)      0.4836 (1.06)      31.2213 (1.23)      0.4400 (1.0)          11;3  31.9760 (0.82)         31           1
test_benchmark_encode_av1              93.8177 (3.77)     105.1013 (3.94)      96.7255 (3.78)      2.5824 (5.68)      96.2374 (3.78)      1.7019 (3.87)          3;2  10.3385 (0.26)         20           1
test_benchmark_encode_kvazaar         134.6820 (5.41)     138.5686 (5.20)     136.1574 (5.33)      1.1093 (2.44)     135.7057 (5.33)      1.3643 (3.10)          6;0   7.3444 (0.19)         20           1
test_benchmark_encode_hevc_pillow     246.7012 (9.91)     465.6218 (17.46)    303.3524 (11.87)    55.4541 (121.88)   280.5991 (11.02)    70.5077 (160.26)        4;1   3.2965 (0.08)         20           1
test_benchmark_encode_hevc            254.3977 (10.22)    367.5713 (13.78)    281.9840 (11.03)    23.4613 (51.57)    278.2842 (10.93)    18.2218 (41.42)         2;1   3.5463 (0.09)         20           1
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
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
- [pybind11](https://github.com/pybind/pybind11) - C++/Python bindings
