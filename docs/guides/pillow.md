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

## Auxiliary Image Extraction & Saving (Depth & Gain Maps)

HEIF files often bundle auxiliary tracks such as metric depth maps, Apple portrait segmentation masks, or HDR gain maps. When using Pillow, these auxiliary channels are accessible directly on `img.info`:

```python
with Image.open("portrait.heic") as img:
    # 1. Check for Depth Map
    if img.info.get("has_depth_image"):
        depth = img.info["depth_map"]
        print(f"Depth dimensions: {depth.width}x{depth.height}")
        print("Depth metadata:", img.info.get("depth_metadata"))

        # Convert to real-world metric depth (float32 meters) if calibrated
        if depth.info and depth.info.has_metric_depth:
            metric_depth = depth.to_metric_depth()

        # Render high-contrast scientific pseudocolor (Turbo colormap)
        # Automatically resize to match master photo dimensions (size=img.size)
        depth_pil = depth.to_pillow(colormap="turbo", size=img.size)
        depth_pil.save("depth_turbo.png")

    # 2. Check for Apple Portrait Matte (hair/subject segmentation alpha)
    if img.info.get("has_portrait_matte"):
        matte = img.info["portrait_matte"]
        matte_pil = matte.to_pillow(colormap="grayscale", size=img.size)
        matte_pil.save("portrait_matte.png")

    # 3. Check for HDR Gain Map
    if img.info.get("has_gain_map") or "gain_map" in img.info:
        gain_map_pil = img.info["gain_map"]
        gain_map_pil.save("gain_map.png")
```

### Saving with Auxiliary Depth Maps

You can save an image with an embedded depth map or portrait matte directly through `img.save()`:

```python
base_image = Image.open("portrait.png")
depth_map = Image.open("depth_map.png").convert("L")

# Save as HEIC with auxiliary depth track
base_image.save(
    "output_with_depth.heic",
    format="HEIF",
    quality=85,
    depth_map=depth_map,
    depth_map_quality=80
)
```
