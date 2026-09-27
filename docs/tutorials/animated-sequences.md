# Creating and Decoding Animated HEIF/AVIF Sequences

Both HEIF and AVIF formats support image sequence tracks (`msf1`, `avis`), allowing animations with full 10-bit color, alpha transparency, and variable frame rates (VFR) at a fraction of the file size of traditional animated GIFs or APNGs.

This tutorial demonstrates:
1. Encoding an animated image sequence with custom per-frame durations.
2. Decoding an animated sequence frame-by-frame.
3. Converting an animated sequence to an animated GIF using Pillow.

---

## 1. Encoding an Animated Sequence

To create an animated sequence, create a visual sequence track on the `HeifContext`, encode successive frames, and set per-frame durations:

```python
import numpy as np
import pylibheif

width, height = 320, 240
num_frames = 30
fps = 24
frame_duration_ms = int(1000 / fps)  # ~41ms per frame

# 1. Initialize context & AV1 sequence encoder
ctx = pylibheif.HeifContext()
encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.AV1)
encoder.apply_preset("fast")
encoder.quality = 75

# 2. Add visual sequence track
track = ctx.add_visual_sequence_track(
    width=width,
    height=height,
    track_type=pylibheif.HeifTrackType.ImageSequence
)

# 3. Generate and append animation frames
for i in range(num_frames):
    # Create animated bouncing circle or graphic
    frame = pylibheif.HeifImage(
        pylibheif.HeifColorspace.RGB,
        pylibheif.HeifChroma.InterleavedRGB24,
        width,
        height
    )
    plane = frame.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    
    # Set per-frame duration in milliseconds
    frame.set_duration(frame_duration_ms)

    # Encode frame into the track
    track.encode_sequence_image(frame, encoder)

# 4. Finalize sequence and write to disk
track.encode_end_of_sequence(encoder)
ctx.write_to_file("animation.avif")
print(f"Created animated AVIF with {num_frames} frames!")
```

---

## 2. Decoding Sequence Frames & Durations

To read an animated container frame-by-frame:

```python
import pylibheif

ctx = pylibheif.HeifContext()
ctx.read_from_file("animation.avif")

# Check if the container contains a sequence track
if not ctx.has_sequence():
    print("This file is a still image, not an animation sequence.")
else:
    # Retrieve the primary track
    track = ctx.get_track(0)
    print(f"Track ID: {track.id}, Width: {track.width}, Height: {track.height}")

    frame_count = 0
    total_duration_ms = 0

    while True:
        try:
            # Decode next frame into RGB24
            image = track.decode_next_image(
                pylibheif.HeifColorspace.RGB,
                pylibheif.HeifChroma.InterleavedRGB24
            )
            duration = image.get_duration()
            total_duration_ms += duration
            frame_count += 1
            print(f"Decoded Frame {frame_count}: duration = {duration} ms")
        except pylibheif.HeifError as e:
            # End_of_sequence error signals animation loop termination
            break

    print(f"Total animation length: {total_duration_ms / 1000.0:.2f} seconds ({frame_count} frames)")
```

---

## 3. Converting Animated AVIF to Animated GIF

You can bridge sequence frames directly into Pillow to export an animated GIF:

```python
from PIL import Image
import pylibheif

ctx = pylibheif.HeifContext()
ctx.read_from_file("animation.avif")
track = ctx.get_track(0)

pil_frames = []
durations = []

while True:
    try:
        frame = track.decode_next_image(
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB24
        )
        pil_img = pylibheif.to_pillow(frame)
        pil_frames.append(pil_img)
        durations.append(frame.get_duration())
    except pylibheif.HeifError:
        break

if pil_frames:
    pil_frames[0].save(
        "converted_animation.gif",
        save_all=True,
        append_images=pil_frames[1:],
        duration=durations,
        loop=0
    )
    print("Successfully converted sequence to animated GIF!")
```
