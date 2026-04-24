import pytest
import numpy as np
import pylibheif
import gc
import os


def test_empty_image_encoding():
    """Test 1: Empty image encoding (width=0 or height=0)"""
    arr_w0 = np.zeros((100, 0, 3), dtype=np.uint8)
    arr_h0 = np.zeros((0, 100, 3), dtype=np.uint8)

    with pytest.raises(pylibheif.HeifError):
        pylibheif.HeifImage.from_numpy(arr_w0)

    with pytest.raises(pylibheif.HeifError):
        pylibheif.HeifImage.from_numpy(arr_h0)


def test_large_image_memory_limits():
    """Test 2: Large image (8K) memory allocation behavior"""
    # Use a large sparse array (mostly zeros) to avoid blowing up memory during test
    # but large enough to trigger the 100MB clamp logic in write_to_bytes
    arr = np.zeros((4320, 7680, 3), dtype=np.uint8)
    # Add some data to ensure it doesn't compress to nothing
    arr[:100, :100, :] = 255

    img = pylibheif.HeifImage.from_numpy(arr)
    ctx = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    enc.encode_image(ctx, img)

    data = ctx.write_to_bytes()
    assert len(data) > 0


def test_read_from_memory_repeated():
    """Test 3: Repeated read_from_memory on same context"""
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    img = pylibheif.HeifImage.from_numpy(arr)
    ctx_write = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    enc.encode_image(ctx_write, img)
    data = ctx_write.write_to_bytes()

    ctx_read = pylibheif.HeifContext()
    ctx_read.read_from_memory(data)

    # Second read on the same context should raise a RuntimeError because of internal protection
    with pytest.raises(RuntimeError, match="Context already initialized"):
        ctx_read.read_from_memory(data)


def test_context_gc_discard():
    """Test 4: Discarding context without writing (GC behavior)"""
    import psutil
    process = psutil.Process(os.getpid())

    gc.collect()
    mem_before = process.memory_info().rss

    # Create and discard many contexts with large images
    for _ in range(50):
        arr = np.zeros((1000, 1000, 3), dtype=np.uint8)
        img = pylibheif.HeifImage.from_numpy(arr)
        ctx = pylibheif.HeifContext()
        enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        enc.encode_image(ctx, img)
        # Deliberately do not write, let it go out of scope

    gc.collect()
    mem_after = process.memory_info().rss

    # Check that we haven't leaked significant memory (e.g. less than 50MB, ignoring slight GC delays)
    assert (mem_after - mem_before) < 50 * 1024 * 1024


def test_from_numpy_invalid_dtypes():
    """Test 5: from_numpy with float32/float64 arrays"""
    arr_f32 = np.zeros((10, 10, 3), dtype=np.float32)
    arr_f64 = np.zeros((10, 10, 3), dtype=np.float64)

    # nanobind does implicit casting if data sizes match, or raises TypeError if strict
    # Since nanobind cast handles float32->uint8 implicitly in some configurations,
    # we use type: ignore or expect valid conversion. If it converts, we just verify it doesn't crash.
    for arr in (arr_f32, arr_f64):
        try:
            img = pylibheif.HeifImage.from_numpy(arr)
            assert img.width == 10
        except TypeError:
            pass  # Also acceptable


def test_high_bit_depth_planes():
    """Test 6: 10-bit / 12-bit image planes return uint16 numpy arrays"""
    # 10-bit RGB
    img = pylibheif.HeifImage(
        10, 10, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )
    img.add_plane(pylibheif.HeifChannel.Interleaved, 10, 10, 10)

    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    arr = np.asarray(plane)

    assert arr.dtype == np.uint16
    assert arr.shape == (10, 10, 3)


def test_ycbcr_color_planes():
    """Test 7: YCbCr colorspace (e.g., YUV420) plane dimensions"""
    # 4:2:0 YCbCr means Cb and Cr are half the width and half the height of Y
    img = pylibheif.HeifImage(
        20, 20, pylibheif.HeifColorspace.YCbCr, pylibheif.HeifChroma.C420
    )

    img.add_plane(pylibheif.HeifChannel.Y, 20, 20, 8)
    img.add_plane(pylibheif.HeifChannel.Cb, 10, 10, 8)
    img.add_plane(pylibheif.HeifChannel.Cr, 10, 10, 8)

    arr_y = np.asarray(img.get_plane(pylibheif.HeifChannel.Y, False))
    arr_cb = np.asarray(img.get_plane(pylibheif.HeifChannel.Cb, False))
    arr_cr = np.asarray(img.get_plane(pylibheif.HeifChannel.Cr, False))

    assert arr_y.shape == (20, 20, 1) or arr_y.shape == (20, 20)
    assert arr_cb.shape == (10, 10, 1) or arr_cb.shape == (10, 10)
    assert arr_cr.shape == (10, 10, 1) or arr_cr.shape == (10, 10)


def test_non_standard_stride():
    """Test 8: Non-standard stride (sliced arrays)"""
    # Create a 20x20x3 array, then take a slice [::2, ::2, :]
    # The resulting array is 10x10x3 but memory is NOT contiguous (not C_CONTIGUOUS)
    base_arr = np.zeros((20, 20, 3), dtype=np.uint8)
    sliced_arr = base_arr[::2, ::2, :]

    assert not sliced_arr.flags["C_CONTIGUOUS"]

    # If nanobind allows it via implicit copy, we ensure it doesn't crash
    try:
        img = pylibheif.HeifImage.from_numpy(sliced_arr)
        assert img.width == 10
    except TypeError:
        # If strict checking is on, this is the expected failure
        pass

    # Making it contiguous via .copy() should definitely work
    contig_arr = np.ascontiguousarray(sliced_arr)
    assert contig_arr.flags["C_CONTIGUOUS"]
    img = pylibheif.HeifImage.from_numpy(contig_arr)
    assert img.width == 10
    assert img.height == 10
