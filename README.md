# pylibheif

Python bindings for [libheif](https://github.com/strukturag/libheif) using pybind11.

## Features

- **HEIC/HEIF Support**: Read and write HEIC images (HEVC/H.265 encoded)
- **AVIF Support**: Read and write AVIF images (AV1 encoded)
- **JPEG2000 Support**: Read and write JPEG2000 images in HEIF container
- **NumPy Integration**: Zero-copy access to image data via Python Buffer Protocol
- **Metadata Support**: Read EXIF and XMP metadata from images
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
# Clone with submodules
git clone --recursive https://github.com/your-username/pylibheif.git
cd pylibheif

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
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

## API Reference

### Classes

- `HeifContext`: Main context for reading/writing HEIF files
- `HeifImageHandle`: Handle to a decoded image with metadata
- `HeifImage`: Raw image data with buffer protocol support
- `HeifEncoder`: Encoder for creating HEIF files
- `HeifPlane`: Image plane with NumPy buffer protocol

### Enums

- `HeifColorspace`: RGB, YCbCr, Monochrome
- `HeifChroma`: C420, C422, C444, InterleavedRGB, InterleavedRGBA
- `HeifChannel`: Y, Cb, Cr, R, G, B, Alpha, Interleaved
- `HeifCompressionFormat`: HEVC, AV1, JPEG, JPEG2000

### Exceptions

- `HeifError`: Base exception for all libheif errors

## Building from Source

```bash
# Clone with submodules
git clone --recursive https://github.com/your-username/pylibheif.git
cd pylibheif

# Build
uv pip install -e .
```

## License

This project is licensed under the LGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [libheif](https://github.com/strukturag/libheif) - HEIF/AVIF codec library
- [pybind11](https://github.com/pybind/pybind11) - C++/Python bindings
