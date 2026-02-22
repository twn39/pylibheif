import os
import gc
import asyncio
import pytest
from concurrent.futures import ThreadPoolExecutor

import pylibheif

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

def get_current_rss_mb():
    if HAS_PSUTIL:
        return psutil.Process().memory_info().rss / (1024 * 1024)
    else:
        # Fallback for platforms with 'ps'
        import subprocess
        out = subprocess.check_output(['ps', '-o', 'rss=', '-p', str(os.getpid())])
        return int(out.strip()) / 1024

def decode_image_sync(path):
    """Synchronously load and decode an image using nanobind wrappers."""
    ctx = pylibheif.HeifContext()
    ctx.read_from_file(path)
    handle = ctx.get_primary_image_handle()
    img = handle.decode(pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB)
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
    # Ensure memory is somewhat accessed
    return plane.shape

@pytest.mark.asyncio
async def test_concurrent_memory_leak():
    """Test memory usage stability under concurrent HEIF decodes."""
    image_path = os.path.join(os.path.dirname(__file__), "..", "images", "test.heic")
    assert os.path.exists(image_path), f"Test image not found at {image_path}"

    # Warmup to initialize Python caches, Pytest internals, and shared libraries
    for _ in range(5):
        decode_image_sync(image_path)
    
    gc.collect()
    mem_before = get_current_rss_mb()
    
    # Run concurrent decodes
    num_tasks = 500
    concurrency = 10
    
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        tasks = [
            loop.run_in_executor(pool, decode_image_sync, image_path)
            for _ in range(num_tasks)
        ]
        await asyncio.gather(*tasks)
        
    gc.collect()
    mem_after = get_current_rss_mb()
    
    growth_mb = mem_after - mem_before
    print(f"\nMemory Tracking for {num_tasks} decodes:")
    print(f"  Memory before: {mem_before:.2f} MB")
    print(f"  Memory after:  {mem_after:.2f} MB")
    print(f"  Memory growth: {growth_mb:.2f} MB")
    
    # Assert memory growth is within a very modest bound (e.g. 150 MB)
    # If the handles/ndarrays were leaking, we'd leak 500 * (image_size) MB easily causing GBs of growth.
    assert growth_mb < 150.0, f"Significant memory leak detected! Growth: {growth_mb:.2f} MB"
