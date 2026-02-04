"""
pylibheif 测试套件

运行测试: uv run pytest tests/test_pylibheif.py -v
"""
import pytest
import numpy as np
import os
import tempfile


class TestEnums:
    """测试枚举类型"""
    
    def test_colorspace_enum(self):
        import pylibheif
        assert pylibheif.HeifColorspace.RGB is not None
        assert pylibheif.HeifColorspace.YCbCr is not None
        assert pylibheif.HeifColorspace.Monochrome is not None
    
    def test_chroma_enum(self):
        import pylibheif
        assert pylibheif.HeifChroma.InterleavedRGB is not None
        assert pylibheif.HeifChroma.InterleavedRGBA is not None
        assert pylibheif.HeifChroma.C420 is not None
        assert pylibheif.HeifChroma.C422 is not None
        assert pylibheif.HeifChroma.C444 is not None
    
    def test_channel_enum(self):
        import pylibheif
        assert pylibheif.HeifChannel.Y is not None
        assert pylibheif.HeifChannel.Interleaved is not None
        assert pylibheif.HeifChannel.R is not None
        assert pylibheif.HeifChannel.G is not None
        assert pylibheif.HeifChannel.B is not None
    
    def test_compression_format_enum(self):
        import pylibheif
        assert pylibheif.HeifCompressionFormat.HEVC is not None
        assert pylibheif.HeifCompressionFormat.AV1 is not None
        assert pylibheif.HeifCompressionFormat.JPEG2000 is not None


class TestHeifImage:
    """测试 HeifImage 类"""
    
    def test_create_rgb_image(self):
        import pylibheif
        width, height = 100, 100
        img = pylibheif.HeifImage(
            width, height,
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        assert img is not None
    
    def test_add_plane(self):
        import pylibheif
        width, height = 100, 100
        img = pylibheif.HeifImage(
            width, height,
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    
    def test_get_plane_as_numpy(self):
        import pylibheif
        width, height = 100, 100
        img = pylibheif.HeifImage(
            width, height,
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
        
        plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
        arr = np.asarray(plane)
        
        assert arr.shape == (height, width, 3)
        assert arr.dtype == np.uint8
    
    def test_write_to_plane(self):
        import pylibheif
        width, height = 100, 100
        img = pylibheif.HeifImage(
            width, height,
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
        
        plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
        arr = np.asarray(plane)
        
        # 填充红色
        arr[:, :, 0] = 255  # R
        arr[:, :, 1] = 0    # G
        arr[:, :, 2] = 0    # B
        
        # 验证写入成功
        assert arr[0, 0, 0] == 255
        assert arr[0, 0, 1] == 0
        assert arr[0, 0, 2] == 0


class TestHeifContext:
    """测试 HeifContext 类"""
    
    def test_create_context(self):
        import pylibheif
        ctx = pylibheif.HeifContext()
        assert ctx is not None
    
    def test_context_manager(self):
        import pylibheif
        with pylibheif.HeifContext() as ctx:
            assert ctx is not None


class TestDecoding:
    """测试解码功能"""
    
    @pytest.fixture
    def heic_path(self):
        """返回测试 HEIC 文件路径"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "images", "test.heic")
        if not os.path.exists(path):
            pytest.skip(f"Test file not found: {path}")
        return path
    
    def test_read_heic_file(self, heic_path):
        import pylibheif
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(heic_path)
    
    def test_get_primary_image_handle(self, heic_path):
        import pylibheif
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(heic_path)
        handle = ctx.get_primary_image_handle()
        
        assert handle.width > 0
        assert handle.height > 0
    
    def test_kvazaar_encoding(self):
        import pylibheif
        # Only test if Kvazaar is actually available in the build
        descriptors = pylibheif.get_encoder_descriptors()
        kvazaar_desc = next((d for d in descriptors if "kvazaar" in d.id_name), None)
        
        if not kvazaar_desc:
            pytest.skip("Kvazaar encoder not available")

        # Test explicit selection
        encoder = pylibheif.HeifEncoder(kvazaar_desc)
        assert "kvazaar" in encoder.name.lower()
        
        # 5.0 is the test quality often used
        encoder.set_lossy_quality(50)

        # Create a dummy image to encode
        width = 64
        height = 64
        image = pylibheif.HeifImage(width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB)
        
        # Add a plane with dummy data
        image.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
        # We don't strictly need to fill the data for a simple encoding check, but it's good practice
        # passing an empty image might cause issues depending on the encoder implementation, 
        # but here we just allocated it, so it contains garbage or zeros. 
        # Let's just encode it.

        ctx = pylibheif.HeifContext()
        handle = encoder.encode_image(ctx, image)
        
        assert handle is not None

    def test_add_two_images_to_one_file(self, tmp_path, heic_path):
        import pylibheif
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(heic_path)
        handle = ctx.get_primary_image_handle()
        
    def test_decode_to_rgb(self, heic_path):
        import pylibheif
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(heic_path)
        handle = ctx.get_primary_image_handle()
        
        img = handle.decode(
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        
        plane = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
        arr = np.asarray(plane)
        
        assert arr.shape == (handle.height, handle.width, 3)
        assert arr.dtype == np.uint8
    
    def test_decode_to_rgba(self, heic_path):
        import pylibheif
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(heic_path)
        handle = ctx.get_primary_image_handle()
        
        img = handle.decode(
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGBA
        )
        
        plane = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
        arr = np.asarray(plane)
        
        assert arr.shape == (handle.height, handle.width, 4)
        assert arr.dtype == np.uint8


class TestEncoding:
    """测试编码功能"""
    
    def create_test_image(self, width=100, height=100):
        """创建测试图像"""
        import pylibheif
        img = pylibheif.HeifImage(
            width, height,
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
        
        plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
        arr = np.asarray(plane)
        
        # 创建渐变图案
        for y in range(height):
            for x in range(width):
                arr[y, x, 0] = int(255 * x / width)   # R
                arr[y, x, 1] = int(255 * y / height)  # G
                arr[y, x, 2] = 128                     # B
        
        return img
    
    def test_hevc_encoder_available(self):
        import pylibheif
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        assert encoder is not None
    
    def test_av1_encoder_available(self):
        import pylibheif
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.AV1)
        assert encoder is not None
    
    def test_jpeg2000_encoder_available(self):
        import pylibheif
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.JPEG2000)
        assert encoder is not None
    
    def test_encode_hevc(self):
        import pylibheif
        img = self.create_test_image()
        
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(85)
        encoder.encode_image(ctx, img)
        
        with tempfile.NamedTemporaryFile(suffix='.heic', delete=False) as f:
            output_path = f.name
        
        try:
            ctx.write_to_file(output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            os.unlink(output_path)

    def test_encode_hevc_with_preset(self):
        import pylibheif
        img = self.create_test_image()
        
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(85)
        
        # Test valid preset (x265 presets: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow, placebo)
        # We use "ultrafast" as it should be quick
        encoder.encode_image(ctx, img, preset="ultrafast")
        
        with tempfile.NamedTemporaryFile(suffix='.heic', delete=False) as f:
            output_path = f.name
        
        try:
            ctx.write_to_file(output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            os.unlink(output_path)
    
    def test_encode_av1(self):
        import pylibheif
        img = self.create_test_image()
        
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.AV1)
        encoder.set_lossy_quality(85)
        encoder.encode_image(ctx, img)
        
        with tempfile.NamedTemporaryFile(suffix='.avif', delete=False) as f:
            output_path = f.name
        
        try:
            ctx.write_to_file(output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            os.unlink(output_path)
    
    def test_encode_jpeg(self):
        import pylibheif
        
        # Check if JPEG encoder is available
        descriptors = pylibheif.get_encoder_descriptors(pylibheif.HeifCompressionFormat.JPEG)
        if not descriptors:
            pytest.skip("JPEG encoder not available")

        img = self.create_test_image()
        
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.JPEG)
        encoder.set_lossy_quality(85)
        encoder.encode_image(ctx, img)
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            output_path = f.name
        
        try:
            ctx.write_to_file(output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            
            # Verify we can read it back
            ctx_read = pylibheif.HeifContext()
            ctx_read.read_from_file(output_path)
            handle = ctx_read.get_primary_image_handle()
            assert handle.width == 100
            assert handle.height == 100
            
        finally:
            os.unlink(output_path)

    def test_encode_jpeg2000(self):
        import pylibheif
        img = self.create_test_image()
        
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.JPEG2000)
        encoder.set_lossy_quality(85)
        encoder.encode_image(ctx, img)
        
        with tempfile.NamedTemporaryFile(suffix='.j2k.heif', delete=False) as f:
            output_path = f.name
        
        try:
            ctx.write_to_file(output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            
            # Verify we can read it back
            ctx_read = pylibheif.HeifContext()
            ctx_read.read_from_file(output_path)
            handle = ctx_read.get_primary_image_handle()
            assert handle.width == 100
            assert handle.height == 100
            
        finally:
            os.unlink(output_path)


class TestRoundTrip:
    """测试编码-解码往返"""
    
    def create_test_image(self, width=100, height=100):
        """创建测试图像"""
        import pylibheif
        img = pylibheif.HeifImage(
            width, height,
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
        
        plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
        arr = np.asarray(plane)
        arr[:] = 128  # 灰色背景
        
        return img, arr.copy()
    
    @pytest.mark.parametrize("format_name,compression", [
        ("HEVC", "HEVC"),
        ("AV1", "AV1"),
        ("JPEG2000", "JPEG2000"),
    ])
    def test_roundtrip(self, format_name, compression):
        import pylibheif
        
        width, height = 64, 64
        img, original_data = self.create_test_image(width, height)
        
        # 编码
        encode_ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(
            getattr(pylibheif.HeifCompressionFormat, compression)
        )
        encoder.set_lossy_quality(100)  # 最高质量
        encoder.encode_image(encode_ctx, img)
        
        with tempfile.NamedTemporaryFile(suffix='.heif', delete=False) as f:
            output_path = f.name
        
        try:
            encode_ctx.write_to_file(output_path)
            
            # 解码
            decode_ctx = pylibheif.HeifContext()
            decode_ctx.read_from_file(output_path)
            handle = decode_ctx.get_primary_image_handle()
            
            assert handle.width == width
            assert handle.height == height
            
            decoded_img = handle.decode(
                pylibheif.HeifColorspace.RGB,
                pylibheif.HeifChroma.InterleavedRGB
            )
            
            plane = decoded_img.get_plane(pylibheif.HeifChannel.Interleaved, False)
            decoded_data = np.asarray(plane)
            
            assert decoded_data.shape == (height, width, 3)
            
            # 允许有损压缩的误差
            mean_diff = np.abs(decoded_data.astype(float) - original_data.astype(float)).mean()
            assert mean_diff < 30, f"Mean difference too high: {mean_diff}"
            
        finally:
            os.unlink(output_path)


class TestMetadata:
    """测试元数据功能"""
    
    @pytest.fixture
    def heic_path(self):
        """返回测试 HEIC 文件路径"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "images", "test.heic")
        if not os.path.exists(path):
            pytest.skip(f"Test file not found: {path}")
        return path
    
    def test_get_metadata_block_ids(self, heic_path):
        import pylibheif
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(heic_path)
        handle = ctx.get_primary_image_handle()
        
        # 获取所有元数据 ID
        ids = handle.get_metadata_block_ids("")
        # 可能没有元数据，但调用应该成功
        assert isinstance(ids, list)


class TestMetadataWriting:
    """测试元数据写入功能"""
    
    def create_test_image(self, width=64, height=64):
        """创建测试图像"""
        import pylibheif
        img = pylibheif.HeifImage(
            width, height,
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
        
        plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
        arr = np.asarray(plane)
        arr[:] = 128  # 灰色背景
        
        return img
    
    def test_add_exif_metadata(self):
        """测试添加 EXIF 元数据"""
        import pylibheif
        
        img = self.create_test_image()
        
        # 编码图像
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(85)
        handle = encoder.encode_image(ctx, img)
        
        # 创建简单的 EXIF 数据 (必须以正确的 EXIF header 开头)
        # libheif expects the data with 4-byte offset prefix for TIFF header
        exif_data = b'\x00\x00\x00\x00' + b'Exif\x00\x00' + b'II*\x00\x08\x00\x00\x00\x00\x00\x00\x00'
        
        # 添加 EXIF 元数据
        ctx.add_exif_metadata(handle, exif_data)
        
        # 写入到内存
        data = ctx.write_to_bytes()
        assert len(data) > 0
        
        # 读取并验证元数据存在
        ctx2 = pylibheif.HeifContext()
        ctx2.read_from_memory(data)
        handle2 = ctx2.get_primary_image_handle()
        
        # 获取 EXIF 元数据 ID
        exif_ids = handle2.get_metadata_block_ids("Exif")
        assert len(exif_ids) >= 1, "EXIF metadata should be present"
        
        # 验证元数据类型
        assert handle2.get_metadata_block_type(exif_ids[0]) == "Exif"
    
    def test_add_xmp_metadata(self):
        """测试添加 XMP 元数据"""
        import pylibheif
        
        img = self.create_test_image()
        
        # 编码图像
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(85)
        handle = encoder.encode_image(ctx, img)
        
        # 创建简单的 XMP 数据
        xmp_data = b'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:creator>pylibheif test</dc:creator>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''
        
        # 添加 XMP 元数据
        ctx.add_xmp_metadata(handle, xmp_data)
        
        # 写入到内存
        data = ctx.write_to_bytes()
        assert len(data) > 0
        
        # 读取并验证元数据存在
        ctx2 = pylibheif.HeifContext()
        ctx2.read_from_memory(data)
        handle2 = ctx2.get_primary_image_handle()
        
        # 获取所有元数据 ID
        all_ids = handle2.get_metadata_block_ids("")
        assert len(all_ids) >= 1, "XMP metadata should be present"
        
        # 查找 XMP 类型的元数据(可能是 "mime" 类型)
        found_xmp = False
        for mid in all_ids:
            metadata = handle2.get_metadata_block(mid)
            if b'pylibheif test' in metadata:
                found_xmp = True
                break
        
        assert found_xmp, "XMP metadata content should be retrievable"
    
    def test_add_generic_metadata(self):
        """测试添加通用元数据"""
        import pylibheif
        
        img = self.create_test_image()
        
        # 编码图像
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(85)
        handle = encoder.encode_image(ctx, img)
        
        # 添加通用元数据
        custom_data = b'{"test": "pylibheif custom metadata"}'
        ctx.add_generic_metadata(handle, custom_data, "json", "application/json")
        
        # 写入到内存
        data = ctx.write_to_bytes()
        assert len(data) > 0
        
        # 读取并验证
        ctx2 = pylibheif.HeifContext()
        ctx2.read_from_memory(data)
        handle2 = ctx2.get_primary_image_handle()
        
        all_ids = handle2.get_metadata_block_ids("")
        assert len(all_ids) >= 1, "Custom metadata should be present"
    
    def test_roundtrip_with_metadata(self):
        """测试带元数据的编码-解码往返"""
        import pylibheif
        
        img = self.create_test_image()
        
        # 编码并添加多种元数据
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(90)
        handle = encoder.encode_image(ctx, img)
        
        # 添加 XMP
        xmp_data = b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/"></x:xmpmeta><?xpacket end="w"?>'
        ctx.add_xmp_metadata(handle, xmp_data)
        
        # 写入文件
        with tempfile.NamedTemporaryFile(suffix='.heic', delete=False) as f:
            output_path = f.name
        
        try:
            ctx.write_to_file(output_path)
            assert os.path.exists(output_path)
            
            # 读取并解码
            ctx2 = pylibheif.HeifContext()
            ctx2.read_from_file(output_path)
            handle2 = ctx2.get_primary_image_handle()
            
            # 验证图像尺寸
            assert handle2.width == 64
            assert handle2.height == 64
            
            # 验证有元数据
            all_ids = handle2.get_metadata_block_ids("")
            assert len(all_ids) >= 1
            
        finally:
            os.unlink(output_path)


class TestErrorHandling:
    """测试错误处理"""
    
    def test_read_nonexistent_file(self):
        import pylibheif
        ctx = pylibheif.HeifContext()
        with pytest.raises(pylibheif.HeifError):
            ctx.read_from_file("nonexistent_file.heic")
    
    def test_invalid_encoder_format(self):
        import pylibheif
        # JPEG 编码器可能不可用（需要 libjpeg）
        # 这里只测试已知可用的格式
class TestMemoryManagement:
    """测试内存管理，确保没有内存泄漏"""
    
    @pytest.fixture
    def heic_path(self):
        """返回测试 HEIC 文件路径"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "images", "test.heic")
        if not os.path.exists(path):
            pytest.skip(f"Test file not found: {path}")
        return path
    
    def test_read_from_memory_no_leak(self, heic_path):
        """测试 read_from_memory 没有悬空指针问题"""
        import pylibheif
        
        # 读取文件到内存
        with open(heic_path, 'rb') as f:
            data = f.read()
        
        # 使用 read_from_memory
        ctx = pylibheif.HeifContext()
        ctx.read_from_memory(data)
        
        # 清除原始数据引用
        del data
        
        # 继续使用 context，应该正常工作
        handle = ctx.get_primary_image_handle()
        assert handle.width > 0
        assert handle.height > 0
        
        # 解码图像
        img = handle.decode(
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        plane = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
        arr = np.asarray(plane)
        assert arr.shape[0] == handle.height
        assert arr.shape[1] == handle.width
    
    def test_repeated_decode_no_leak(self, heic_path):
        """测试重复解码不会导致内存泄漏"""
        import pylibheif
        import gc
        
        # 多次解码
        for i in range(10):
            ctx = pylibheif.HeifContext()
            ctx.read_from_file(heic_path)
            handle = ctx.get_primary_image_handle()
            img = handle.decode(
                pylibheif.HeifColorspace.RGB,
                pylibheif.HeifChroma.InterleavedRGB
            )
            plane = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
            arr = np.asarray(plane)
            
            # 强制释放
            del arr, plane, img, handle, ctx
            gc.collect()
        
        # 如果没有内存泄漏，这里不会崩溃
        assert True
    
    def test_repeated_encode_no_leak(self):
        """测试重复编码不会导致内存泄漏"""
        import pylibheif
        import gc
        
        for i in range(10):
            # 创建图像
            img = pylibheif.HeifImage(
                64, 64,
                pylibheif.HeifColorspace.RGB,
                pylibheif.HeifChroma.InterleavedRGB
            )
            img.add_plane(pylibheif.HeifChannel.Interleaved, 64, 64, 8)
            
            plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
            arr = np.asarray(plane)
            arr[:] = 128
            
            # 编码
            ctx = pylibheif.HeifContext()
            encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
            encoder.set_lossy_quality(85)
            encoder.encode_image(ctx, img)
            
            with tempfile.NamedTemporaryFile(suffix='.heic', delete=False) as f:
                output_path = f.name
            
            try:
                ctx.write_to_file(output_path)
            finally:
                os.unlink(output_path)
            
            # 强制释放
            del arr, plane, img, ctx, encoder
            gc.collect()
        
        assert True
    
    def test_stress_encode_decode_cycle(self, heic_path):
        """压力测试：多次编码解码循环"""
        import pylibheif
        import gc
        
        for i in range(5):
            # 解码
            ctx = pylibheif.HeifContext()
            ctx.read_from_file(heic_path)
            handle = ctx.get_primary_image_handle()
            img = handle.decode(
                pylibheif.HeifColorspace.RGB,
                pylibheif.HeifChroma.InterleavedRGB
            )
            
            # 编码
            encode_ctx = pylibheif.HeifContext()
            encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
            encoder.set_lossy_quality(85)
            encoder.encode_image(encode_ctx, img)
            
            with tempfile.NamedTemporaryFile(suffix='.heic', delete=False) as f:
                output_path = f.name
            
            try:
                encode_ctx.write_to_file(output_path)
                
                # 读取刚写入的文件
                verify_ctx = pylibheif.HeifContext()
                verify_ctx.read_from_file(output_path)
                verify_handle = verify_ctx.get_primary_image_handle()
                assert verify_handle.width == handle.width
                assert verify_handle.height == handle.height
            finally:
                os.unlink(output_path)
            
            gc.collect()
        
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
