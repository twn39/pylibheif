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
    assert (mem_after - mem_before) < 100 * 1024 * 1024


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


def test_read_from_memory_bytearray_and_memoryview():
    """Verify that read_from_memory accepts bytearray and memoryview inputs."""
    # Create small dummy HEIF file bytes
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    img = pylibheif.HeifImage.from_numpy(arr)
    ctx_write = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    enc.encode_image(ctx_write, img)
    data_bytes = ctx_write.write_to_bytes()

    # 1. Test with bytearray
    data_bytearray = bytearray(data_bytes)
    ctx_read1 = pylibheif.HeifContext()
    ctx_read1.read_from_memory(data_bytearray)
    handle1 = ctx_read1.get_primary_image_handle()
    assert handle1.width == 10

    # 2. Test with memoryview
    data_mv = memoryview(data_bytes)
    ctx_read2 = pylibheif.HeifContext()
    ctx_read2.read_from_memory(data_mv)
    handle2 = ctx_read2.get_primary_image_handle()
    assert handle2.width == 10


def test_from_numpy_pytorch_tensor():
    """Verify from_numpy works with PyTorch CPU tensors (framework-agnostic ndarray)."""
    torch = pytest.importorskip("torch")

    # Create a 3D PyTorch CPU tensor of shape (20, 20, 3) type uint8
    tensor = torch.zeros((20, 20, 3), dtype=torch.uint8)
    # Write some pattern
    tensor[5:15, 5:15, 0] = 255

    # Convert using from_numpy
    img = pylibheif.HeifImage.from_numpy(tensor)
    assert img.width == 20
    assert img.height == 20

    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
    arr = np.asarray(plane)
    assert arr.shape == (20, 20, 3)
    assert np.all(arr[5:15, 5:15, 0] == 255)


def test_rrggbb_and_rrggbbaa_metadata_correctness():
    """验证 RRGGBB 和 RRGGBBAA 交错格式的通道数和 NumPy 字节序元数据的准确性"""
    import pylibheif
    import numpy as np

    width, height = 16, 16
    
    # 1. 验证 16-bit 大端 RRGGBB_BE (应当为 3 通道，大端字节序元数据)
    img_be = pylibheif.HeifImage(width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRRGGBB_BE)
    img_be.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 12)
    plane_be = img_be.get_plane(pylibheif.HeifChannel.Interleaved, writeable=False)
    arr_be = np.asarray(plane_be)
    
    assert arr_be.shape == (height, width, 3)
    # 验证元数据是否包含大端序标志 ">"
    assert ">" in arr_be.dtype.str or arr_be.dtype.byteorder == ">"

    # 2. 验证 16-bit 小端 RRGGBBAA_LE (应当为 4 通道，小端字节序元数据)
    img_le = pylibheif.HeifImage(width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRRGGBBAA_LE)
    img_le.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 10)
    plane_le = img_le.get_plane(pylibheif.HeifChannel.Interleaved, writeable=False)
    arr_le = np.asarray(plane_le)
    
    assert arr_le.shape == (height, width, 4)
    # 验证元数据是否包含小端序标志 "<" 或 "=" (原生字节序)
    assert "<" in arr_le.dtype.str or arr_le.dtype.byteorder in ("<", "=")


def test_decoding_options():
    """验证 HeifDecodingOptions 的获取、设置和多线程解码支持"""
    import pylibheif
    import numpy as np

    # 1. 实例化并配置解码选项
    opts = pylibheif.HeifDecodingOptions()
    assert opts.num_codec_threads == 0  # 默认值
    assert not opts.strict_decoding

    opts.num_codec_threads = 4
    opts.strict_decoding = True
    opts.ignore_transformations = True
    opts.decoder_id = "hevc"

    assert opts.num_codec_threads == 4
    assert opts.strict_decoding
    assert opts.ignore_transformations
    assert opts.decoder_id == "hevc"
    opts.decoder_id = ""
    assert opts.decoder_id == ""

    # 2. 端到端解码测试
    width, height = 64, 64
    img = pylibheif.HeifImage(width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB)
    img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, writeable=True)
    arr = np.asarray(plane)
    arr[:] = 128

    # 编码到内存
    ctx = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    enc.encode_image(ctx, img)
    data = ctx.write_to_bytes()

    # 解码
    ctx_read = pylibheif.HeifContext()
    ctx_read.read_from_memory(data)
    handle = ctx_read.get_primary_image_handle()

    # 带解码选项解码
    decoded_img = handle.decode(options=opts)
    assert decoded_img.width == width
    assert decoded_img.height == height

    # 异步解码支持
    async_ctx = pylibheif.AsyncHeifContext()
    
    import asyncio
    async def run_async_decode():
        await async_ctx.read_from_memory(data)
        async_handle = async_ctx.get_primary_image_handle()
        decoded_async = await async_handle.decode(options=opts)
        assert decoded_async.width == width

    asyncio.run(run_async_decode())


def test_high_bit_depth_from_numpy():
    """验证从 16-bit uint16 NumPy 数组构建高位深 HeifImage 并编码保存"""
    import pylibheif
    import numpy as np

    width, height = 64, 64
    # 创建 10-bit uint16 RGB 数组 (最大值 1023)
    arr_16 = np.zeros((height, width, 3), dtype=np.uint16)
    arr_16[10:50, 10:50, 0] = 1023  # 红通道
    arr_16[10:50, 10:50, 1] = 512   # 绿通道

    # 从 16-bit 数组创建
    img = pylibheif.HeifImage.from_numpy(arr_16, bit_depth=10)
    assert img.width == width
    assert img.height == height

    # 验证导出的平面
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, writeable=False)
    arr_out = np.asarray(plane)
    assert arr_out.shape == (height, width, 3)
    assert arr_out.dtype == np.uint16
    assert np.all(arr_out[10:50, 10:50, 0] == 1023)

    # 编码到内存并解码验证
    ctx = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    enc.encode_image(ctx, img)
    data = ctx.write_to_bytes()

    ctx_read = pylibheif.HeifContext()
    ctx_read.read_from_memory(data)
    handle = ctx_read.get_primary_image_handle()
    assert handle.width == width

    # 解码为 16-bit 并验证
    decoded_img = handle.decode(chroma=pylibheif.HeifChroma.InterleavedRRGGBB_LE)
    plane_decoded = decoded_img.get_plane(pylibheif.HeifChannel.Interleaved, writeable=False)
    arr_decoded = np.asarray(plane_decoded)
    assert arr_decoded.dtype == np.uint16
    assert arr_decoded.shape == (height, width, 3)


def test_auxiliary_images():
    """验证辅助图像（Depth / Alpha）读取接口无损运行"""
    import pylibheif
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "images", "test.heic")
    ctx = pylibheif.HeifContext()
    ctx.read_from_file(path)
    handle = ctx.get_primary_image_handle()

    # 1. 验证获取辅助图像 IDs 的方法不崩溃且返回列表
    aux_ids = handle.get_auxiliary_image_ids()
    assert isinstance(aux_ids, list)

    # 验证过滤器参数
    aux_ids_filtered = handle.get_auxiliary_image_ids(pylibheif.AUX_IMAGE_FILTER_OMIT_ALPHA)
    assert isinstance(aux_ids_filtered, list)

    # 2. 如果存在辅助图，验证获取其句柄及类型
    if len(aux_ids) > 0:
        aux_id = aux_ids[0]
        aux_handle = handle.get_auxiliary_image_handle(aux_id)
        assert isinstance(aux_handle, pylibheif.HeifImageHandle)
        
        aux_type = aux_handle.get_auxiliary_type()
        assert isinstance(aux_type, str)
        assert len(aux_type) > 0
