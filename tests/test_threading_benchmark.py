import os
import pytest
import pylibheif
import numpy as np
import threading
import time


@pytest.fixture
def sample_image_rgb():
    """Create a 1920x1080 RGB image for testing"""
    width, height = 1920, 1080
    # Create a gradient image
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xv, yv = np.meshgrid(x, y)

    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :, 0] = (xv * 255).astype(np.uint8)
    img[:, :, 1] = (yv * 255).astype(np.uint8)
    img[:, :, 2] = 128

    heif_img = pylibheif.HeifImage(
        width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )
    heif_img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    plane = heif_img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    np_plane = np.asarray(plane)
    np_plane[:] = img

    return heif_img


def encode_task(image, quality=50):
    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    encoder.set_lossy_quality(quality)
    encoder.encode_image(ctx, image)
    # Write to bytes to simulate full I/O pipeline
    _ = ctx.write_to_bytes()


@pytest.mark.skipif(
    os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true",
    reason="Skipping threading benchmark in CI",
)
def test_threading_speedup(sample_image_rgb):
    """
    Verify that multi-threaded encoding is faster than sequential encoding.
    This confirms that the GIL is correctly released during heavy C++ operations.
    """
    num_tasks = 4

    # --- Sequential Execution ---
    start_seq = time.time()
    for _ in range(num_tasks):
        encode_task(sample_image_rgb)
    end_seq = time.time()
    time_seq = end_seq - start_seq

    # --- Parallel Execution ---
    threads = []
    start_par = time.time()
    for _ in range(num_tasks):
        t = threading.Thread(target=encode_task, args=(sample_image_rgb,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    end_par = time.time()
    time_par = end_par - start_par

    speedup = time_seq / time_par

    print(f"\nSequential Time: {time_seq:.4f}s")
    print(f"Parallel Time:   {time_par:.4f}s")
    print(f"Speedup: {speedup:.2f}x")

    # We expect some speedup.
    # On loaded machines or strictly single-core environments, this might be lower,
    # but for a dev machine, > 1.1x is a conservative lower bound if GIL is released.
    # If GIL was NOT released, speedup would be ~1.0x (or slightly less due to overhead).
    assert speedup > 1.1, f"Expected parallelism speedup > 1.1, got {speedup:.2f}"
