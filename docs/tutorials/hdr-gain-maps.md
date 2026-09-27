# Mastering HDR Gain Maps: From iPhone HEIC to Reconstructed HDR

Apple iPhones (since iPhone 12 Pro) and Android devices with Ultra HDR capture high-dynamic-range photos by storing an **SDR base image** alongside an auxiliary **Gain Map** channel and metadata conforming to **ISO 21496-1** or Apple's proprietary specification.

This allows standard displays to render the SDR image normally, while HDR displays (OLED, mini-LED, XDR) boost highlight brightness using the gain map.

This tutorial covers the end-to-end workflow:
1. Detecting and extracting Gain Maps.
2. Inspecting physical headroom and transfer parameters.
3. Reconstructing full dynamic range HDR images (Linear Float32 and PQ).
4. Generating and encoding a compliant ISO 21496-1 Gain Map image.

---

## 1. Detecting & Extracting the Gain Map

```python
import pylibheif
import numpy as np

# Load HEIC image from an iPhone
ctx = pylibheif.HeifContext()
ctx.read_from_file("iphone_hdr_photo.heic")

primary_handle = ctx.get_primary_image_handle()

# Check for gain map
if not primary_handle.has_gain_map():
    print("No HDR gain map found in this image.")
else:
    print(f"Base Image: {primary_handle.width}x{primary_handle.height}")
    
    # Retrieve handle to the gain map auxiliary image
    gm_handle = primary_handle.get_gain_map_handle()
    print(f"Gain Map Size: {gm_handle.width}x{gm_handle.height}")
```

---

## 2. Reading Gain Map Metadata

`GainMapMetadata` defines how the gain map pixels are mapped to optical linear luminance boosts:

```python
from pylibheif.gain_map import parse_gain_map_metadata

metadata = primary_handle.get_gain_map_metadata()

print(f"Max HDR Headroom: {metadata.max_hdr_headroom:.2f} stops (EV)")
print(f"Min HDR Headroom: {metadata.min_hdr_headroom:.2f} stops")
print(f"Gain Map Min:     {metadata.gain_map_min}")
print(f"Gain Map Max:     {metadata.gain_map_max}")
print(f"Gamma:            {metadata.gamma}")
```

---

## 3. Reconstructing High-Dynamic-Range Images

`pylibheif` provides hardware-accelerated C++ reconstruction routines (`src/gain_map_accel.cpp`) to combine the SDR base image and the gain map into an HDR pixel buffer:

### Reconstructing Linear Floating-Point HDR

```python
from pylibheif.gain_map import reconstruct_hdr

# Reconstruct into linear scene-referred RGB with target headroom of 2.0 stops
hdr_linear = reconstruct_hdr(
    primary_handle,
    target_headroom=2.0,
    output_format="linear"
)

print("Linear HDR array shape:", hdr_linear.shape)
print("Pixel values can exceed 1.0 in specular highlights:", hdr_linear.max())
```

### Reconstructing BT.2100 PQ (Perceptual Quantizer)

For outputting 10-bit HDR video frames or HDR10 displays:

```python
# Reconstruct directly into ITU-R BT.2100 PQ 16-bit unsigned integers
hdr_pq = reconstruct_hdr(
    primary_handle,
    target_headroom=2.0,
    output_format="pq"
)

print("PQ HDR 16-bit array shape:", hdr_pq.shape, "dtype:", hdr_pq.dtype)
```

---

## 4. Encoding a Custom Image with an ISO 21496-1 Gain Map

You can attach a custom computed gain map (e.g. from an exposure bracket or computational photography algorithm) and encode an ISO 21496-1 compatible HEIF file:

```python
import pylibheif
from pylibheif.gain_map import GainMapMetadata, generate_gain_map_xmp, URN_GAIN_MAP_ISO_21496_1

# 1. Create Base SDR image and Gain Map image
width, height = 1920, 1080
gm_width, gm_height = width // 2, height // 2

base_img = pylibheif.HeifImage(pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB24, width, height)
base_img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

gain_map_img = pylibheif.HeifImage(pylibheif.HeifColorspace.Monochrome, pylibheif.HeifChroma.Monochrome, gm_width, gm_height)
gain_map_img.add_plane(pylibheif.HeifChannel.Y, gm_width, gm_height, 8)

# 2. Setup context & encoders
ctx = pylibheif.HeifContext()
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

# Encode base image
base_handle = ctx.encode_image(base_img, encoder)

# Encode gain map as a secondary image
gm_handle = ctx.encode_image(gain_map_img, encoder)

# 3. Associate the gain map with the base image using ISO 21496-1 URN
ctx.assign_auxiliary_image(
    master_image=base_handle,
    auxiliary_image=gm_handle,
    auxiliary_type=URN_GAIN_MAP_ISO_21496_1
)

# 4. Attach ISO 21496-1 Gain Map XMP metadata to the gain map handle
meta = GainMapMetadata(max_hdr_headroom=2.5, min_hdr_headroom=0.0)
xmp_bytes = generate_gain_map_xmp(meta)
ctx.add_xmp_metadata(gm_handle, xmp_bytes)

# 5. Export to disk
ctx.write_to_file("my_custom_gain_map.heic")
print("Saved ISO 21496-1 Ultra HDR HEIF file!")
```
