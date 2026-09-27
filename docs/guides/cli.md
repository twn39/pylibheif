# Command-Line Interface (CLI)

`pylibheif` includes a high-performance CLI accessible under the commands `heif`, `heic`, or `pylibheif`.

```bash
# Check installed CLI
heif --help
```

---

## 1. Inspecting Images (`info`)

Inspect image metadata, dimensions, color profiles, EXIF/XMP, and camera shooting settings with rich terminal formatting:

```bash
# Basic summary table
heif info image.heic

# Detailed inspection including EXIF tags, GPS, and HDR metadata
heif info image.heic --detail

# Machine-readable JSON output for automated scripting
heif info image.heic --json
```

Example JSON output snippet:
```json
{
  "filename": "photo.heic",
  "width": 4032,
  "height": 3024,
  "bit_depth": 8,
  "has_alpha": false,
  "color_profile": "Display P3",
  "has_gain_map": true,
  "shooting_info": {
    "camera": "Apple iPhone 15 Pro",
    "iso": 50,
    "f_number": 1.78,
    "exposure_time": "1/120s"
  }
}
```

---

## 2. Converting Formats (`convert`)

Convert between HEIF, AVIF, JPEG, and PNG formats with quality and speed presets:

```bash
# Convert HEIC to AVIF with fast preset
heif convert input.heic output.avif --preset fast --quality 80

# Convert JPEG to HEIC with balanced preset
heif convert input.jpg output.heic --preset balanced --quality 85

# Convert with specific color space conversion
heif convert input.heic output.png --srgb

# Extract embedded depth map or portrait matte alongside conversion
heif convert input.heic output.jpg --extract-depth depth_map.png
```

### Supported Speed Presets
- `ultrafast`: Maximum compression throughput, ideal for real-time proxies.
- `fast`: Excellent trade-off between CPU utilization and filesize.
- `balanced`: Default balanced preset.
- `quality`: Maximum compression efficiency and detail preservation.

---

## 3. Environment & Codec Diagnostics (`doctor`)

Check your environment for installed codecs, hardware acceleration flags, CPU thread detection, and library version details:

```bash
heif doctor

# Output as JSON
heif doctor --json
```

---

## 4. Metadata Dumping (`metadata`)

Dump raw EXIF, XMP, or ICC profiles directly from the image:

```bash
# Dump raw EXIF payload
heif metadata dump image.heic --type exif

# Extract raw ICC profile to file
heif metadata dump image.heic --type icc --output profile.icc
```
