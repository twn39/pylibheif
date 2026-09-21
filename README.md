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
- **Stream I/O**: High-performance streaming read and write directly to/from Python file-like stream objects (`BytesIO`, file streams) with >300k OPS
- **Zero-Copy Memory Export**: Export encoded HEIF binaries directly as read-only Python `memoryview` with decoupled lifetime (`write_to_memoryview()`), eliminating memory copies
- **NumPy Integration**: Zero-copy bidirectional access to image plane data via Python Buffer Protocol
- **Pillow (PIL) Integration**: Native opener/saver plugin (`register_pillow_opener()`), lossless pipeline, transparent EXIF/XMP metadata forwarding
- **Unified Speed Presets & Concurrency**: Cross-codec presets (`ultrafast`, `fast`, `balanced`, `quality`), AOM AV1 auto-multithreading with `auto-tiles`, and parameter safety introspection
- **Adaptive Codec Multithreading**: Automatic CPU quota detection (cgroups v1/v2 support) with global thread configuration
- **Metadata Support**: Read and write EXIF, XMP, and custom metadata
- **HDR Metadata Support**: Read and write HDR metadata (CLLI, MDCV, AMVE) using physical units (Nits, Lux, CIE coordinates) with type safety
- **HDR Gain Map & Tonemapping (ISO 21496-1, Apple, Ultra HDR)**: Hardware-accelerated multi-threaded C++ SIMD fusion kernel (~15x speedup, ~28ms for 4MP) and vectorized NumPy 256-LUT engine for HDR reconstruction (Linear, sRGB, Rec.2100 PQ/HDR10)
- **Asynchronous Support**: Built-in dedicated thread-pool `asyncio` wrappers (`AsyncHeifContext`, `AsyncHeifEncoder`) for non-blocking I/O and encoding
- **Command-Line Interface (CLI)**: High-performance, agent-friendly CLI (`heif`, `heic`, `pylibheif`) with batch conversions, directory recursive mirroring (`-r`), multi-process worker pools (`--jobs`), incremental skipping (`--skip-existing`), rich terminal inspection, dynamic progress tracking, and machine-readable structured JSON manifests (`--json`)
- **RAII Resource Management**: Automatic resource cleanup with context managers and lifecycle safety guarantees

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
# Core package (includes full CLI: heif, heic, pylibheif)
pip install pylibheif

# With optional Pillow integration
pip install "pylibheif[pillow]"
```

Or with uv:
```bash
uv pip install "pylibheif[pillow]"
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

# Encode and save as HEIC (defaults to 'balanced' preset: ~38% faster than libheif default)
ctx = pylibheif.HeifContext()
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC, preset="fast")
encoder.set_lossy_quality(85)
encoder.encode_image(ctx, img)

ctx.write_to_file('output.heic')
```

### Writing AVIF Images (AV1)

`pylibheif` automatically enables tile multithreading (`auto-tiles=True` and `threads=N`) for AV1 encoding, delivering up to 32.5% faster encoding speeds:

```python
import pylibheif
import numpy as np

# Prepare image (same as above)
width, height = 1920, 1080
img = pylibheif.HeifImage(width, height, 
                          pylibheif.HeifColorspace.RGB,
                          pylibheif.HeifChroma.InterleavedRGB)
img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

# Encode and save as AVIF with cross-codec preset ('ultrafast', 'fast', 'balanced', 'quality')
ctx = pylibheif.HeifContext()
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.AV1, preset="fast")
encoder.set_lossy_quality(85)
encoder.encode_image(ctx, img)

ctx.write_to_file('output.avif')
```

### Zero-Copy Memory Export (`write_to_memoryview`)

Export encoded HEIF/AVIF binaries directly as a Python standard `memoryview` without intermediate `memcpy` or memory spike doubling:

```python
import pylibheif
import hashlib
import io

with pylibheif.HeifContext() as ctx:
    # ... encode image into ctx ...
    encoder.encode_image(ctx, img)
    
    # 1. Zero-copy read-only memoryview export (0 memcpy, 50% lower peak memory)
    mv = ctx.write_to_memoryview()
    print(f"Exported {len(mv)} bytes, readonly: {mv.readonly}")
    
    # 2. Or use write_to_bytes with copy=False
    mv_same = ctx.write_to_bytes(copy=False)
    
# Lifecycle Safety: `mv` remains 100% valid and safe even after ctx is closed!
# Directly consume in zero-copy pipelines:
bio = io.BytesIO(mv)                     # Stream buffer without extra copy
sha256 = hashlib.sha256(mv).hexdigest()  # Compute checksum directly on C++ memory
```

### Stream I/O (`BytesIO`, Network & File Streams)

Read and write directly to and from Python file-like stream objects supporting `read()`, `seek()`, `tell()`, or `write()`:

```python
import pylibheif
import io

# 1. Stream Write (exceeds 300,000 OPS)
stream_out = io.BytesIO()
with pylibheif.HeifContext() as ctx:
    encoder.encode_image(ctx, img)
    ctx.write_to_stream(stream_out)

# 2. Stream Read
stream_out.seek(0)
with pylibheif.HeifContext() as ctx:
    ctx.read_from_stream(stream_out)
    handle = ctx.get_primary_image_handle()
    decoded = handle.decode()
```

### Pillow (PIL) First-Class Integration

`pylibheif` provides native, first-class Pillow integration with zero-copy decoding pipelines, transparent metadata forwarding, and high-performance saving capabilities.

#### 1. Quick Registration & Opening

Enable `pylibheif` as Pillow's default codec for HEIC, HEIF, and AVIF formats with a single call:

```python
from PIL import Image
import pylibheif

# Register pylibheif as Pillow's HEIF / AVIF opener and saver
pylibheif.register_pillow_opener()

# Open HEIC / AVIF using standard Pillow API (zero-copy decoder)
im = Image.open('photo.heic')
print(f"Format: {im.format}, Size: {im.size}, Mode: {im.mode}")

# Transparent access to EXIF, XMP, and ICC Profile
raw_exif = im.info.get('exif')         # Raw EXIF bytes (ready for Pillow Exif or Piexif)
xmp_bytes = im.info.get('xmp')         # Raw XMP XML bytes
icc_prof = im.info.get('icc_profile')  # Color profile bytes

# Auxiliary image access (Depth Maps & HDR Gain Maps)
depth_img = im.info.get('depth_image')  # PIL.Image.Image of the depth map (if present)
gain_map = im.info.get('gain_map')      # PIL.Image.Image of the HDR gain map (if present)
```

#### 2. Advanced Saving with Speed Presets & Codec Controls

Save images directly using `im.save()` with fine-grained control over encoder performance:

```python
# Fast encoding with cross-codec presets ('ultrafast', 'fast', 'balanced', 'quality')
im.save('output_fast.heic', preset='fast', quality=85)

# High-speed AVIF encoding with multithreading
im.save('output.avif', speed=8, threads=4, quality=80)

# Mathematically lossless HEIC/AVIF encoding
im.save('lossless.heic', lossless=True)  # or quality=-1

# Forward custom raw encoder parameters (e.g. x265 or AOM options)
im.save('custom.heic', enc_params={'tune': 'ssim'})

# Preserve or modify metadata upon save
im.save('with_meta.heic', exif=raw_exif, xmp=xmp_bytes)
```

#### 3. Zero-Copy Bidirectional Conversions

Convert back and forth between Pillow `Image` and `pylibheif.HeifImage` without intermediate disk I/O:

```python
# Convert Pillow Image -> HeifImage (zero-copy numpy buffer protocol)
heif_image, metadata_dict = pylibheif.from_pillow(im, bit_depth=8)

# Convert HeifImage or HeifImageHandle -> Pillow Image
pil_img = pylibheif.to_pillow(heif_image)
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

### HDR Gain Map & Tonemapping (ISO 21496-1)

`pylibheif` provides native, end-to-end processing for High-Dynamic Range (HDR) Gain Maps compliant with **ISO 21496-1**, **Apple HDRGainMap**, and **Adobe/Google Ultra HDR** specifications. It features a multi-tiered acceleration engine:
- **Tier 1 (NumPy)**: Fast vectorized 256-entry float32 sRGB EOTF lookup table (`_SRGB_TO_LINEAR_LUT_256`), monochrome dimension reduction, in-place math, and hardware `np.exp2`.
- **Tier 2 (Native C++ SIMD)**: Multi-threaded single-pass fused kernel via nanobind ndarray zero-copy buffer protocol, releasing the GIL across all CPU cores for **~15x speedup** (~28ms for 4MP images).

#### 1. Inspecting and Extracting Gain Maps

```python
from pylibheif import gain_map
import pylibheif

with pylibheif.HeifContext() as ctx:
    ctx.read_from_file('photo.heic')
    
    # Check if image contains an auxiliary HDR gain map
    if gain_map.has_gain_map(ctx):
        # Extract GainMap metadata (min/max stops, gamma, SDR/HDR offsets)
        meta = gain_map.parse_gain_map_metadata(ctx)
        print(f"Max HDR headroom boost: 2^{meta.gain_map_max[0]:.2f}x ({meta.gain_map_max[0]:.2f} stops)")
        print(f"Is monochrome: {meta.is_monochrome}, Gamma: {meta.gamma}")
        
        # Extract auxiliary gain map as PIL Image
        gain_map_img = gain_map.extract_gain_map(ctx)
```

#### 2. Hardware-Accelerated HDR Image Reconstruction

Reconstruct full HDR imagery by blending the SDR base image with the auxiliary gain map according to target display headroom:

```python
import numpy as np
from pylibheif import gain_map

# Base SDR image (H, W, 3/4 uint8) and Gain Map (H, W uint8 or H, W, 3 uint8)
sdr_rgb = ...  # uint8 NumPy array
gain_map_arr = ...  # uint8 NumPy array
metadata = gain_map.parse_gain_map_metadata('photo.heic')

# Reconstruct HDR appearance (automatically uses Tier 2 C++ SIMD kernel if available)
# Supported output_format:
# - 'srgb_clip': Standard sRGB uint8 clamped tonemapping preview
# - 'linear': Linear float32 HDR scene radiance
# - 'pq': 10-bit Rec.2100 PQ (HDR10) uint16 array for HDR displays
hdr_srgb = gain_map.reconstruct_hdr_image(
    sdr_rgb,
    gain_map_arr,
    metadata,
    target_headroom=4.0,  # 4x brightness boost factor
    output_format="srgb_clip",
)

# Generate 10-bit Rec.2100 PQ HDR10 output
hdr_pq_10bit = gain_map.reconstruct_hdr_image(
    sdr_rgb,
    gain_map_arr,
    metadata,
    target_headroom=4.0,
    output_format="pq",
)
```

#### 3. Seamless Pillow Gain Map Integration

```python
from PIL import Image
import pylibheif

pylibheif.register_pillow_opener()

# Open photo containing gain map
im = Image.open('apple_hdr_photo.heic')

# Direct access to auxiliary gain map and parsed metadata
gain_img = im.info.get('gain_map')              # PIL.Image.Image (gain map)
gain_meta = im.info.get('gain_map_metadata')    # GainMapMetadata object
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

## Command-Line Interface (CLI)

`pylibheif` includes a high-performance command-line interface tailored for developers and **AI agents**, registered under three convenient aliases:
- **`heif`**: Primary concise command (covers HEIC, AVIF, JPEG2000).
- **`heic`**: Direct intuitive alias for Apple HEIC photos and day-to-day conversion.
- **`pylibheif`**: Canonical package-matching command for strict CI/CD scripts.

All query commands support `--json` (`-j`) for pure, machine-readable JSON output to stdout.

### 1. Inspect Image Properties (`info`)

Inspect dimensions, color channels, bit depth, color profile, HDR tags, shooting metadata, and embedded blocks (supports single images, wildcard patterns, and entire directories):

```bash
# Pretty terminal output with tables (automatically parses Camera, Lens, Exposure, and GPS)
heif info photo.heic
# or intuitively:
heic info photo.heic

# Full inspection: expands complete EXIF tags table and syntax-highlighted XMP/MIME XML panel
heic info photo.heic --detail

# Inspect an entire directory of photos in a unified overview table
heif info ./photos/

# Recursively discover and inspect images across nested subdirectories
heif info ./photos/ --recursive

# Machine-readable JSON output (single file or array for directories, ideal for AI agents)
heic info photo.heic --json
heic info ./photos/ --json
```

<details>
<summary><b>Sample Terminal Output (<code>heic info photo.heic</code>)</b></summary>

```text
                     Image Information: photo.heic                     
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Property        ┃ Value                                                ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Resolution      │ 5992 x 3994                                          │
│ Bit Depth       │ 8-bit (chroma: 8-bit)                                │
│ Alpha Channel   │ No                                                   │
│ File Size       │ 2.4 MB (2584969 bytes)                               │
│ Images in File  │ 1 (primary id: 43)                                   │
│ Thumbnails      │ 0                                                    │
│ Depth Map       │ No                                                   │
│ Gain Map (HDR)  │ No                                                   │
│ Color Profile   │ Prof                                                 │
│ Camera / Device │ Apple iPhone 16 (iPhone 16 back camera 5.96mm f/1.6) │
│ Date Taken      │ 2026:09:13 19:44:46 +08:00                           │
│ Exposure        │ 35mm · f/1.6 · 1/17s · ISO 400                       │
│ GPS Location    │ (31.0, 7.0, 16.17) N, (121.0, 32.0, 30.52) E         │
│ Metadata        │ EXIF: Yes | XMP: Yes | Blocks: 2                     │
│ HDR Metadata    │ CLLI (Max: 203 nits)                                 │
└─────────────────┴──────────────────────────────────────────────────────┘
```
</details>

<details>
<summary><b>Sample JSON Output (<code>heic info photo.heic --json</code>)</b></summary>

```json
{
  "file": "/path/to/photo.heic",
  "size_bytes": 2584969,
  "width": 5992,
  "height": 3994,
  "has_alpha": false,
  "bit_depth": 8,
  "chroma_bits_per_pixel": 8,
  "total_images": 1,
  "primary_image_id": 43,
  "thumbnails_count": 0,
  "has_depth_image": false,
  "has_gain_map": false,
  "color_profile": {
    "type": "Prof",
    "has_icc": true,
    "has_nclx": false
  },
  "metadata_summary": {
    "has_exif": true,
    "has_xmp": true,
    "total_blocks": 2
  },
  "shooting_info": {
    "Camera": "Apple iPhone 16 (iPhone 16 back camera 5.96mm f/1.6)",
    "Date Taken": "2026:09:13 19:44:46 +08:00",
    "Exposure": "35mm · f/1.6 · 1/17s · ISO 400",
    "GPS Location": "(31.0, 7.0, 16.17) N, (121.0, 32.0, 30.52) E (Alt: 4.2m)"
  },
  "hdr": {
    "clli": {
      "max_content_light_level": 203,
      "max_pic_average_light_level": 50
    }
  }
}
```
</details>

### 2. Format Conversion & Transcoding (`convert`)

Convert seamlessly between HEIC, AVIF, JPEG, and PNG formats with quality, speed controls, and batch multiprocessing:

```bash
# 1. Single-file conversion (classic mode)
heif convert input.heic output.avif --preset fast --quality 75
heif convert input.jpg output.heic --preset balanced --quality 85

# 2. Parallel batch conversion across worker processes
# Discovers all supported images and encodes in parallel using ProcessPoolExecutor
heif convert ./photos/ -o ./converted/ --format avif --jobs 4 --preset fast --quality 80

# 3. Recursive directory mirroring & incremental sync
# Mirrors subdirectory structure into target output and skips already converted files
heif convert ./raw_photos/ -o ./optimized/ --format heic -r --skip-existing

# 4. Filter by specific extensions
heif convert ./raw_photos/ -o ./avif_out/ --format avif --ext ".heic,.jpg"

# 5. Gain Map auxiliary extraction & HDR tonemapped rendering
heif convert photo.heic preview.jpg --render-hdr --hdr-headroom 3.0
heif convert photo.heic preview.png --extract-gain-map gainmap.png

# 6. Safety: Prevent accidental overwrites (use -y / --overwrite to replace)
heif convert input.heic output.avif -y

# 7. Machine-readable JSON Batch Manifest (designed for AI agents and CI/CD pipelines)
heif convert ./photos/ -o ./converted/ --format avif --json
```

<details>
<summary><b>Sample Batch JSON Manifest (<code>heif convert ./photos/ -o ./converted/ --format avif --json</code>)</b></summary>

```json
{
  "summary": {
    "total": 12,
    "succeeded": 11,
    "skipped": 1,
    "failed": 0,
    "elapsed_seconds": 1.45,
    "images_per_second": 7.59,
    "total_original_bytes": 28434600,
    "total_converted_bytes": 14217300,
    "space_saved_bytes": 14217300,
    "compression_ratio_percent": 50.0
  },
  "results": [
    {
      "source": "/path/to/photos/img01.heic",
      "target": "/path/to/converted/img01.avif",
      "status": "success",
      "format": "avif",
      "elapsed_seconds": 0.12,
      "source_size_bytes": 2369550,
      "target_size_bytes": 1184775,
      "compression_ratio_percent": 50.0
    }
  ]
}
```
</details>

### 3. Environment & Codec Diagnostics (`doctor`)

Check host environment capabilities, installed encoders, CPU thread quotas, and Pillow integration:

```bash
# Rich diagnostics panel
heif doctor

# Structured JSON for environment discovery
heif doctor --json
```

### 4. Metadata Inspection & Direct Preview (`metadata`)

Directly preview EXIF tags, GPS coordinates, and XMP XML text in your terminal, or extract raw binaries:

```bash
# In-place preview: prints metadata blocks summary, EXIF tags table, GPS table, and syntax-highlighted XMP XML
heic metadata dump photo.heic

# Machine-readable JSON tree with parsed EXIF tags and decoded UTF-8 XMP content
heic metadata dump photo.heic --json

# Extract raw EXIF or XMP binary to a separate file
heif metadata extract photo.heic --type exif --out photo_exif.bin -y
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
Reads a HEIF file from a bytes-like object (`bytes`, `bytearray`, `memoryview`).
- `data`: Bytes-like buffer containing the file content.

**`read_from_stream(stream: Any) -> None`**
Reads HEIF data directly from a Python file-like stream object implementing `read()`, `seek()`, `tell()`.
- `stream`: A stream object such as `io.BytesIO` or `open('...', 'rb')`.

**`write_to_file(filename: str) -> None`**
Writes the current context to a file.
- `filename`: Destination path.

**`write_to_bytes(copy: bool = True) -> bytes | memoryview`**
Writes the current context to binary output.
- `copy`: If `True` (default), returns a standard immutable Python `bytes` object (involves one memory copy). If `False`, returns a zero-copy read-only `memoryview`.

**`write_to_memoryview() -> memoryview`**
Directly exports the encoded HEIF binary data as a zero-copy read-only Python `memoryview`.
- Fully lifecycle-safe (backed by an internal C++ capsule that persists even after context closure).
- Eliminates memory copies and avoids memory peak doubling.

**`write_to_stream(stream: Any) -> None`**
Writes HEIF data directly to a Python file-like stream object implementing `write()`.
- `stream`: A writable stream object such as `io.BytesIO` or `open('...', 'wb')`.

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

#### Properties

- **`parameters`** *(HeifEncoderParametersProxy)*: A dictionary-like interface providing access to all configurable encoder parameters. It dynamically routes settings to the correct type-safe setters with validation.

#### Methods

**`__init__(format_or_descriptor: Union[HeifCompressionFormat, HeifEncoderDescriptor], preset: str = "")`**
Creates a new encoder with an optional speed preset.
- `format_or_descriptor`: Compression format or specific encoder descriptor.
- `preset`: Initial preset ("ultrafast", "fast", "balanced", "quality"). If omitted, uses global default preset (`"balanced"`).

**`apply_preset(preset: str) -> None`**
Applies a cross-codec preset. Automatically maps to native parameters (`x265: preset`, `aom: speed + threads + auto-tiles`) and introspects parameter support to safely avoid unsupported parameter exceptions.

**`has_parameter(name: str) -> bool`**
Checks whether the current encoder supports a given parameter name.

**`set_parameters(params: dict[str, str]) -> None`**
Sets multiple encoder parameters in batch from a dictionary.

**`set_lossy_quality(quality: int) -> None`**
Sets the quality for lossy compression (0-100).

**`set_lossless(lossless: bool) -> None`**
Enables or disables lossless compression.

**`set_parameter(name: str, value: str) -> None`**
Sets a low-level encoder parameter as a string.

**`get_parameter(name: str) -> str`**
Gets the string representation of a parameter value.

**`set_integer_parameter(name: str, value: int) -> None`**
**`get_integer_parameter(name: str) -> int`**
**`set_boolean_parameter(name: str, value: bool) -> None`**
**`get_boolean_parameter(name: str) -> bool`**
**`set_string_parameter(name: str, value: str) -> None`**
**`get_string_parameter(name: str) -> str`**
Type-safe getters and setters for parameter values.

**`encode_image(context: HeifContext, image: HeifImage, preset: str = "") -> HeifImageHandle`**
Encodes the given image and appends it to the context.
- `context`: Destination `HeifContext`.
- `image`: Source `HeifImage` to encode.
- `preset`: Optional encoder preset override ("ultrafast", "fast", "balanced", "quality"). Safe across all codecs (x265, aom, kvazaar).

---

### Encoder Parameters Introspection

`pylibheif` supports inspecting and dynamically validating encoder parameters at runtime using `encoder.parameters`.

#### class `pylibheif.HeifEncoderParameter`

Describes a parameter supported by the selected encoder.

- **`name`** *(str)*: Parameter name.
- **`type`** *(HeifEncoderParameterType)*: Data type of the parameter (Integer, Boolean, or String).
- **`has_default`** *(bool)*: Whether the parameter has a default value.
- **`default_value`** *(Union[int, bool, str, None])*: The default value.
- **`valid_integer_range`** *(Optional[Tuple[int, int]])*: Min and max allowed integers if bounded.
- **`valid_integer_values`** *(Optional[List[int]])*: Specific allowed integers.
- **`valid_string_values`** *(Optional[List[str]])*: Specific allowed string choices.

#### enum `pylibheif.HeifEncoderParameterType`

- `Integer`
- `Boolean`
- `String`

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

Asynchronous wrapper for `HeifContext`. Operations are awaited and offloaded to a background thread pool executor without blocking the asyncio event loop.

#### Methods

**`async from_file(filename: str) -> AsyncHeifContext`**  
**`async from_memory(data: bytes) -> AsyncHeifContext`**  
**`async from_stream(stream: Any) -> AsyncHeifContext`**  
Asynchronous factory methods to construct and read context.

**`async read_from_file(filename: str) -> None`**  
**`async read_from_memory(data: bytes) -> None`**  
**`async read_from_stream(stream: Any) -> None`**  
**`async write_to_file(filename: str) -> None`**  
**`async write_to_bytes(copy: bool = True) -> bytes | memoryview`**  
**`async write_to_memoryview() -> memoryview`**  
**`async write_to_stream(stream: Any) -> None`**  
**`get_primary_image_handle() -> AsyncHeifImageHandle`**  
**`get_image_handle(id: int) -> AsyncHeifImageHandle`**  

---

### Global Functions & Configuration

#### Codec Multithreading & Presets
- **`get_default_encoder_preset() -> str`**: Gets the global default encoder preset (`"balanced"` by default).
- **`set_default_encoder_preset(preset: str) -> None`**: Sets the global default encoder preset (`"ultrafast"`, `"fast"`, `"balanced"`, `"quality"`). Can also be configured via `PYLIBHEIF_ENCODER_PRESET` environment variable.
- **`get_default_num_threads() -> int`**: Gets default codec threads for decode operations (auto-detected from CPU count and cgroup limits).
- **`set_default_num_threads(threads: int) -> None`**: Sets default codec threads (0 resets to adaptive auto-detection).
- **`get_default_codec_executor()` / `set_default_codec_executor()` / `shutdown_default_codec_executor()`**: Manages the dedicated background thread pool for async codec tasks.

#### Pillow Interoperability
- **`register_pillow_opener()` / `unregister_pillow_opener()`**: Registers or unregisters `pylibheif` as Pillow's HEIF/AVIF image opener and saver.
- **`to_pillow(source, convert_hdr_to_8bit=True) -> PIL.Image.Image`**: Converts `HeifImage` or `HeifImageHandle` into a Pillow `Image`.
- **`from_pillow(pil_image: PIL.Image.Image, bit_depth: int = 8) -> HeifImage`**: Converts a Pillow `Image` into a `HeifImage`.

---

### class `pylibheif.AsyncHeifImageHandle`

Asynchronous wrapper for `HeifImageHandle`.

#### Methods

**`async decode(colorspace, chroma) -> HeifImage`**
Asynchronously decodes the image.

---

### class `pylibheif.AsyncHeifEncoder`

Asynchronous wrapper for `HeifEncoder`.

#### Properties

- **`parameters`** *(HeifEncoderParametersProxy)*: Synchronous dictionary-like proxy to access and set encoder parameters.

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

Benchmarks on 1920x1080 (HD) RGB real-world images (Apple Silicon), comparing python libraries and codecs.

| Operation | Library / Encoder / Feature | Mean Time | Throughput |
|:---|:---|:---:|:---:|
| **Stream Write** | `pylibheif` (64KB buffered stream) | **3.18 μs** | **314,076 OPS** |
| **Stream Read** | `pylibheif` (zero-copy readinto) | **8.10 μs** | **123,445 OPS** |
| **Decoding** | `pylibheif` (HEVC parallel, 4 threads) | **60.90 ms** | 16.42 OPS |
| **Decoding** | `pillow-heif` | ~61.41 ms | 16.28 OPS |
| **Decoding** | `pylibheif` (HEVC default) | ~62.02 ms | 16.12 OPS |
| **Encoding** | `pylibheif` / Kvazaar (Q80) | **177.52 ms** | 5.63 OPS |
| **Encoding** | `pillow-heif` / x265 (Q80) | ~245.65 ms | 4.07 OPS |
| **Encoding** | `pylibheif` / x265 (Q80, balanced) | ~263.61 ms | 3.79 OPS |
| **Encoding** | `pylibheif` / AV1 (AOM, speed=6 balanced) | ~268.61 ms | 3.72 OPS |

### Key Findings:

1.  **Ultra-Fast Stream I/O**: The C++ buffered stream adapter with 64KB chunks and redundant seek elimination delivers microsecond-level overhead (**3.18 μs write, 8.10 μs read**) with zero-copy buffer integration, exceeding 314k OPS.
2.  **Decoding Parity & Parallelism**: `pylibheif` delivers direct zero-copy decode speeds (~60.9 ms with 4 codec threads, ~62.0 ms default) fully matching specialized PIL extensions while providing direct access to native pointers and NumPy arrays without intermediate copies.
3.  **HEVC Encoding Performance**: The bundled `kvazaar` encoder significantly outperforms x265 (~177 ms vs ~245-263 ms) with identical lossy quality and seamless API integration.
4.  **AV1 Speed Optimization**: With automatic tile threading and speed preset mapping, `pylibheif` brings AV1 encoding down from ~292 ms to ~268 ms on 1080p frames.

### HDR Gain Map (ISO 21496-1) Reconstruction Benchmarks

Benchmarked on 4-Megapixel (2000x2000) real-world image datasets (Apple Silicon, M-series):

| Operation / Kernel | Mean Time | Throughput | Speedup vs NumPy | Memory Footprint |
|:---|:---:|:---:|:---:|:---:|
| **C++ Multi-threaded SIMD Kernel** (`gain_map_accel`) | **28.85 ms** | **138.6 Mpx/s** | **15.01x** | **Zero heap allocation (in-place)** |
| **NumPy Vectorized Pipeline** (Tier 1 256-LUT) | 433.12 ms | 9.2 Mpx/s | 1.00x (baseline) | Peak reduced by 60% |
| **Naive Python float loop / unvectorized** | ~3,200 ms | 1.2 Mpx/s | 0.13x | High GC overhead |

### CLI Multi-Process Batch Throughput

`heif convert` with parallel worker processes (`--jobs` / `-j`) scales near-linearly across CPU cores by leveraging `ProcessPoolExecutor`, isolating native codec heaps and bypassing the Python GIL:
- **Scalability**: Linear speedups on multi-core workstations and server CPUs (e.g. 4-8x faster bulk conversion).
- **Incremental Sync**: `--skip-existing` avoids re-encoding existing target files, enabling robust resume for terabyte-scale photo archives.

<details>
<summary><b>Raw Benchmark Output (Apple M Series)</b></summary>

```text
-----------------------------------------------------------------------------------------------------------------------------------
Name                                                 Mean            OPS  Comment
-----------------------------------------------------------------------------------------------------------------------------------
test_benchmark_stream_write_performance           3.18 μs     314,076.00  (pylibheif 64KB buffered stream write)
test_benchmark_stream_read_performance            8.10 μs     123,444.82  (pylibheif zero-copy stream read)
test_benchmark_gain_map_reconstruct_cpp          28.85 ms          34.66  (C++ SIMD multi-threaded fused kernel)
test_benchmark_decode_hevc_parallel              60.90 ms          16.42  (pylibheif 4-thread decode)
test_benchmark_decode_hevc_pillow                61.41 ms          16.28  (pillow-heif)
test_benchmark_decode_hevc                       62.02 ms          16.12  (pylibheif direct decode)
test_benchmark_encode_kvazaar                   177.52 ms           5.63  (pylibheif, kvazaar, Q80)
test_benchmark_encode_hevc_pillow               245.65 ms           4.07  (pillow-heif, x265, Q80)
test_benchmark_encode_hevc                      263.61 ms           3.79  (pylibheif, x265, Q80)
test_benchmark_encode_av1                       268.61 ms           3.72  (pylibheif, aom, speed=6)
test_benchmark_gain_map_reconstruct_numpy       433.12 ms           2.31  (NumPy vectorized 256-LUT pipeline)
-----------------------------------------------------------------------------------------------------------------------------------
```

</details>

Run benchmarks yourself:
```bash
uv pip install pillow-heif pytest-benchmark
uv run pytest tests/test_benchmark.py tests/test_stream_benchmark.py --benchmark-only --benchmark-min-rounds=20
```

## License

This project is licensed under the LGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [libheif](https://github.com/strukturag/libheif) - HEIF/AVIF codec library
- [nanobind](https://nanobind.readthedocs.io) - Modern C++/Python bindings
