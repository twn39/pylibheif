# Pillow (PIL) Integration

`pylibheif` provides first-class, seamless integration with [Pillow](https://python-pillow.org/). Pillow is strictly an **optional** dependency; `pylibheif` operates fully without it.

---

## Automatic Opener & Saver Registration

By calling `register_pillow_opener()`, Pillow gains native support for opening and saving `.heic`, `.heif`, and `.avif` files.

```python
import pylibheif
from PIL import Image

# Register the plugin
pylibheif.register_pillow_opener()

# Open any HEIF/HEIC or AVIF image
with Image.open("sample.heic") as img:
    print(img.format)       # "HEIF"
    print(img.size)         # (4032, 3024)
    print(img.mode)         # "RGB"
    
    # Save as AVIF with preset
    img.save("sample.avif", quality=80, preset="fast")
```

To clean up or unregister the handler:
```python
pylibheif.unregister_pillow_opener()
```

---

## Bidirectional Zero-Copy Conversion

When working with existing `pylibheif.HeifImage` instances, you can convert back and forth between Pillow `Image` objects:

=== "HeifImage to Pillow"

    ```python
    import pylibheif

    ctx = pylibheif.HeifContext()
    ctx.read_from_file("photo.heic")
    handle = ctx.get_primary_image_handle()
    heif_img = handle.decode(pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB24)

    # Convert to PIL.Image
    pil_img = pylibheif.to_pillow(heif_img)
    pil_img.show()
    ```

=== "Pillow to HeifImage"

    ```python
    from PIL import Image
    import pylibheif

    pil_img = Image.open("photo.png")
    
    # Convert directly to HeifImage
    heif_img = pylibheif.from_pillow(pil_img)
    ```

---

## Metadata Preservation (EXIF, XMP, ICC)

When opening an image through the Pillow plugin, camera metadata is fully preserved inside `img.info`:

- `img.info["exif"]`: Raw EXIF bytes (with TIFF header offsets normalized).
- `img.info["xmp"]`: Embedded XMP metadata string or bytes.
- `img.info["icc_profile"]`: Color profile binary bytes.
- `img.info["nclx"]`: Normalized Color NCLX parameters dictionary.

When saving via `img.save()`, you can forward these parameters:

```python
img.save(
    "output.heic",
    quality=90,
    preset="balanced",
    exif=img.info.get("exif"),
    icc_profile=img.info.get("icc_profile")
)
```

---

## Auxiliary Image Extraction (Depth & Gain Maps)

HEIF files often bundle auxiliary tracks such as depth maps or Apple HDR gain maps. When using Pillow:

```python
with Image.open("portrait.heic") as img:
    # Check for depth map
    if "depth_image" in img.info:
        depth_pil = img.info["depth_image"]
        depth_pil.save("depth.png")

    # Check for gain map
    if "gain_map" in img.info:
        gain_map_pil = img.info["gain_map"]
        gain_map_pil.save("gain_map.png")
```
