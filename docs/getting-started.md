# Getting Started

## Installation

`pylibheif` comes with bundled `libheif`, `kvazaar` (HEVC encoder), and `dav1d` (AV1 decoder) submodules compiled directly into the binary wheels.

=== "Using uv (Recommended)"

    ```bash
    # Install core package
    uv pip install pylibheif

    # Install with Pillow integration and CLI
    uv pip install "pylibheif[all]"
    ```

=== "Using pip"

    ```bash
    # Install with all optional dependencies (Pillow + CLI)
    pip install "pylibheif[all]"
    ```

---

## Basic Concepts

`pylibheif` structures image processing into four clear abstractions:

1. **`HeifContext`**: The container managing file, memory, or stream access, tracks, and metadata.
2. **`HeifImageHandle`**: An uncompressed reference to an image or auxiliary track inside the container, containing dimensions, color profile info, and EXIF/XMP metadata.
3. **`HeifImage`**: The decompressed pixel data represented across planar or interleaved channels.
4. **`HeifEncoder`**: The compression engine configuring codec profiles, speed presets, thread pools, and quality levels.

---

## Decoding an Image

To read and decompress an image:

```python
import pylibheif

# 1. Initialize context and load file
ctx = pylibheif.HeifContext()
ctx.read_from_file("input.heic")

# 2. Retrieve handle to the primary image
handle = ctx.get_primary_image_handle()
print(f"Dimensions: {handle.width}x{handle.height}")
print(f"Alpha channel: {handle.has_alpha}")
print(f"Bit depth: {handle.luma_bits_per_pixel} bits")

# 3. Decode into interleaved RGB24 format
image = handle.decode(
    pylibheif.HeifColorspace.RGB,
    pylibheif.HeifChroma.InterleavedRGB24
)

# 4. Access plane memory
plane = image.get_plane(pylibheif.HeifChannel.Interleaved)
print(f"Plane stride: {plane.stride} bytes, data length: {len(plane.data)}")
```

---

## Zero-Copy NumPy Interoperability

`pylibheif.HeifPlane` implements the Python Buffer Protocol (`Py_buffer`). You can wrap decoded planes directly in `numpy.ndarray` with zero memory copies:

```python
import numpy as np
import pylibheif

ctx = pylibheif.HeifContext()
ctx.read_from_file("input.heic")
handle = ctx.get_primary_image_handle()
image = handle.decode(pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB24)

plane = image.get_plane(pylibheif.HeifChannel.Interleaved)

# Zero-copy view into native C++ allocated plane memory
array = np.asarray(plane)
print(f"NumPy array shape: {array.shape}, dtype: {array.dtype}")
```

---

## Encoding an Image

To encode an image with custom compression settings:

```python
import pylibheif

# 1. Create a blank image (e.g. 1920x1080 RGB)
width, height = 1920, 1080
image = pylibheif.HeifImage(
    pylibheif.HeifColorspace.RGB,
    pylibheif.HeifChroma.InterleavedRGB24,
    width,
    height
)
plane = image.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

# Fill plane with data (e.g., solid gray)
plane_data = memoryview(plane.data)
# (Write pixels into plane_data...)

# 2. Setup context and encoder
ctx = pylibheif.HeifContext()
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

# Configure speed preset and quality
encoder.apply_preset("fast")
encoder.quality = 85

# 3. Encode image into context
ctx.encode_image(image, encoder)

# 4. Save to disk
ctx.write_to_file("output.heic")
```
