# Working with Depth Maps & Auxiliary Images

HEIF containers support embedding auxiliary image tracks linked to a master image. Typical examples include:
- **Portrait Depth Maps**: Stored by Apple and Android cameras to simulate shallow depth of field (bokeh).
- **Alpha Transparency Mattes**: Fine segmentation masks separating subjects from backgrounds.
- **Custom AI Masks**: Salient object segmentations or thermal imaging channels.

This tutorial demonstrates how to read, visualize, process, and write auxiliary depth tracks.

---

## 1. Extracting and Visualizing Depth Maps

`pylibheif` provides a first-class `DepthMap` domain entity accessible directly on image handles via `handle.depth_map`. It encapsulates decoding, physical unit conversion (ISO/IEC 23008-12 / ITU-T H.265), and microsecond pseudocolor visualization without requiring OpenCV or Matplotlib.

```python
import pylibheif
import numpy as np

ctx = pylibheif.HeifContext()
ctx.read_from_file("portrait_photo.heic")
master_handle = ctx.get_primary_image_handle()

# Check for depth map via domain property
if master_handle.depth_map is not None:
    depth = master_handle.depth_map
    print(f"Master size: {master_handle.width}x{master_handle.height}")
    print(f"Depth size:  {depth.info.width}x{depth.info.height}")
    print(f"Bit depth:   {depth.info.bit_depth} bits")
    print(f"Type:        {depth.representation_type.name}")

    # Inspect physical metric depth range (if calibrated metadata is present)
    if depth.info.has_metric_depth:
        print(f"Physical range: {depth.info.near_distance:.2f}m ~ {depth.info.far_distance:.2f}m")
        # Convert to real-world metric distance in meters (float32 2D ndarray)
        metric_depth = depth.to_metric_depth()
        print(f"Center pixel distance: {metric_depth[depth.info.height // 2, depth.info.width // 2]:.2f} meters")

    # 1. Decode to normalized float32 [0.0, 1.0] NumPy array (0=closest, 1=farthest)
    depth_array = depth.decode(normalize=True)

    # 2. Render directly to a PIL Image with high-contrast scientific pseudocolor
    # Supported colormaps: "turbo" (default), "inferno", "viridis", "grayscale"
    # Zero external dependencies: uses precomputed 768-byte palette LUT (<0.1ms)
    depth_pil = depth.to_pillow(colormap="turbo")
    depth_pil.save("extracted_depth_turbo.png")
```

### Apple Portrait Matte Masks

For photos captured on iPhones with Apple portrait segmentation, access the alpha subject matte directly via `handle.portrait_matte`:

```python
if master_handle.portrait_matte is not None:
    matte_image = master_handle.portrait_matte.decode()
    matte_pil = master_handle.portrait_matte.to_pillow(colormap="grayscale")
    matte_pil.save("portrait_matte.png")
```

---

## 2. Applying Synthetic Bokeh Blur Using Depth

Using OpenCV and the decoded depth map, you can dynamically apply Gaussian blur to background pixels based on their camera distance:

```python
import cv2
import numpy as np
import pylibheif

# 1. Decode master image (RGB)
ctx = pylibheif.HeifContext()
ctx.read_from_file("portrait_photo.heic")
master = ctx.get_primary_image_handle()
color_img = master.decode(pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB24)
color_array = np.asarray(color_img.get_plane(pylibheif.HeifChannel.Interleaved))

# 2. Decode normalized depth map directly using DepthMap entity
# Returns float32 array in [0.0, 1.0] where 0.0=foreground, 1.0=background
depth_array = master.depth_map.decode(normalize=True)
depth_resized = cv2.resize(depth_array, (master.width, master.height))

# 3. Create depth-of-field blur mask
# Pixels further away (higher normalized values) receive full Gaussian blur
blurred_bg = cv2.GaussianBlur(color_array, (31, 31), 0)

# Reshape mask for 3-channel alpha blending
alpha_mask = depth_resized[:, :, np.newaxis]

# Alpha blend: in-focus foreground + blurred background
bokeh_result = (color_array * (1.0 - alpha_mask) + blurred_bg * alpha_mask).astype(np.uint8)

cv2.imwrite("portrait_bokeh.jpg", cv2.cvtColor(bokeh_result, cv2.COLOR_RGB2BGR))
```

---

## 3. Writing Auxiliary Images (`assign_auxiliary_image`)

`pylibheif` provides `ctx.assign_auxiliary_image()` to attach any custom encoded image (e.g. depth map, matte mask) as an auxiliary track to a master image:

```python
import pylibheif

# Setup context & HEVC encoder
ctx = pylibheif.HeifContext()
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

# 1. Encode primary master image (RGB 1920x1080)
master_img = pylibheif.HeifImage(pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB24, 1920, 1080)
master_img.add_plane(pylibheif.HeifChannel.Interleaved, 1920, 1080, 8)
# (Fill master_img with pixel data...)
master_handle = ctx.encode_image(master_img, encoder)

# 2. Encode auxiliary depth map (Monochrome 960x540)
depth_img = pylibheif.HeifImage(pylibheif.HeifColorspace.Monochrome, pylibheif.HeifChroma.Monochrome, 960, 540)
depth_img.add_plane(pylibheif.HeifChannel.Y, 960, 540, 8)
# (Fill depth_img with depth data...)
depth_handle = ctx.encode_image(depth_img, encoder)

# 3. Assign as auxiliary track
# The auxiliary image is automatically marked as hidden (infe.hidden_item=true)
# and linked via standard 'auxl' and 'auxC' reference boxes.
ctx.assign_auxiliary_image(
    master_image=master_handle,
    auxiliary_image=depth_handle,
    auxiliary_type="urn:mpeg:hevc:2015:auxid:1"
)

# 4. Save container
ctx.write_to_file("output_with_depth.heic")
print("Saved HEIF image with embedded auxiliary depth track!")
```
