# Color Science & HDR

`pylibheif` provides comprehensive color management, physical-unit HDR metadata handling, and Ultra HDR Gain Map decoding/reconstruction conforming to ISO 21496-1 and Apple specifications.

---

## Color Profiles & NCLX Parsing

Color in HEIF/AVIF images is defined either via an embedded **ICC Profile** or via **NCLX Color Primaries** (ITU-R BT.2100 / BT.709).

```python
import pylibheif

ctx = pylibheif.HeifContext()
ctx.read_from_file("photo.heic")
handle = ctx.get_primary_image_handle()

# Check profile type
profile_type = handle.get_color_profile_type()
if profile_type == pylibheif.HeifColorProfileType.Nclx:
    nclx = handle.get_nclx_color_profile()
    print("Color Primaries:", nclx.color_primaries)
    print("Transfer Characteristics:", nclx.transfer_characteristics)
    print("Matrix Coefficients:", nclx.matrix_coefficients)
elif profile_type == pylibheif.HeifColorProfileType.Prof:
    icc_bytes = handle.get_raw_color_profile()
    print(f"ICC Profile size: {len(icc_bytes)} bytes")
```

### Profile Synthesis & Cross-Conversion

`pylibheif.color` provides utilities to synthesize standard ICC profiles and convert between NCLX descriptors:

```python
from pylibheif.color import nclx_to_icc_profile, DISPLAY_P3_ICC_BYTES, SRGB_ICC_BYTES

# Synthesize ICC profile directly from NCLX metadata
icc = nclx_to_icc_profile(nclx)
```

---

## Physical HDR Metadata (CLLI, MDCV, AMVE)

`pylibheif` supports reading and writing physical unit representations of HDR metadata:

- **CLLI (Content Light Level Information)**:
  - `max_content_light_level` (in cd/m²)
  - `max_pic_average_light_level` (in cd/m²)
- **MDCV (Mastering Display Colour Volume)**:
  - Display primaries $(x, y)$, white point $(x, y)$, `max_luminance`, `min_luminance`.
- **AMVE (Ambient Viewing Environment)**:
  - Ambient illuminance (lux) and ambient white point.

```python
if handle.has_content_light_level:
    clli = handle.content_light_level
    print(f"Max CLL: {clli.max_content_light_level} nits")

if handle.has_mastering_display_colour_volume:
    mdcv = handle.mastering_display_colour_volume
    print(f"Mastering Max Luminance: {mdcv.max_luminance} nits")
```

---

## ISO 21496-1 & Apple HDR Gain Maps

Modern smartphones (Apple iPhone, Android Ultra HDR) store a standard dynamic range (SDR) base image alongside an auxiliary **Gain Map** and metadata describing the HDR headroom.

### Inspecting Gain Map Metadata

```python
from pylibheif.gain_map import parse_gain_map_metadata

if handle.has_gain_map():
    gm_handle = handle.get_gain_map_handle()
    metadata = handle.get_gain_map_metadata()
    
    print(f"Gain Map Size: {gm_handle.width}x{gm_handle.height}")
    print(f"HDR Headroom: {metadata.max_hdr_headroom:.2f} EV")
```

### Reconstructing Full HDR Image

You can reconstruct high-dynamic range linear float or PQ pixel buffers from the base image and gain map:

```python
from pylibheif.gain_map import reconstruct_hdr

# Reconstruct HDR linear floating-point or PQ image
hdr_array = reconstruct_hdr(handle, target_headroom=2.0)
```
