# Working with Depth Maps & Auxiliary Images

HEIF containers support embedding auxiliary image tracks linked to a master image. Typical examples include:
- **Portrait Depth Maps**: Stored by Apple and Android cameras to simulate shallow depth of field (bokeh).
- **Alpha Transparency Mattes**: Fine segmentation masks separating subjects from backgrounds.
- **Custom AI Masks**: Salient object segmentations or thermal imaging channels.

This tutorial demonstrates how to read, visualize, process, and write auxiliary depth tracks.

---

## 1. Extracting and Visualizing Depth Maps

When Apple iPhones take photos in Portrait Mode, the depth map is stored as an auxiliary channel with `urn:mpeg:hevc:2015:auxid:1` (or Apple's proprietary portrait depth URN).

```python
import pylibheif
import numpy as np
from PIL import Image

ctx = pylibheif.HeifContext()
ctx.read_from_file("portrait_photo.heic")
master_handle = ctx.get_primary_image_handle()

# Check for depth map
if master_handle.has_depth_image:
    print("Found portrait depth map!")
    
    # Retrieve depth handle
    depth_handle = master_handle.get_depth_image_handle()
    print(f"Master size: {master_handle.width}x{master_handle.height}")
    print(f"Depth size:  {depth_handle.width}x{depth_handle.height}")

    # Decode depth map to monochrome pixel plane
    depth_image = depth_handle.decode(
        pylibheif.HeifColorspace.Monochrome,
        pylibheif.HeifChroma.Monochrome
    )
    
    # Zero-copy conversion into a NumPy 2D array
    depth_plane = depth_image.get_plane(pylibheif.HeifChannel.Y)
    depth_array = np.asarray(depth_plane)
    
    # Save as grayscale visualization image
    depth_vis = Image.fromarray(depth_array)
    depth_vis.save("extracted_depth.png")
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

# 2. Decode depth map and resize to match color dimensions
depth = master.get_depth_image_handle()
depth_img = depth.decode(pylibheif.HeifColorspace.Monochrome, pylibheif.HeifChroma.Monochrome)
depth_array = np.asarray(depth_img.get_plane(pylibheif.HeifChannel.Y))
depth_resized = cv2.resize(depth_array, (master.width, master.height))

# 3. Create depth-of-field blur mask
# Pixels further away (lower/higher depth values depending on camera) receive more blur
blurred_bg = cv2.GaussianBlur(color_array, (25, 25), 0)

# Normalize depth mask to 0.0 - 1.0 float
alpha_mask = (depth_resized.astype(np.float32) / 255.0)[:, :, np.newaxis]

# Alpha blend: in-focus foreground + blurred background
bokeh_result = (color_array * alpha_mask + blurred_bg * (1.0 - alpha_mask)).astype(np.uint8)

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
