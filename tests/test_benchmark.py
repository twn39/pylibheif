
import pytest
import pylibheif
import numpy as np
import os

class TestBenchmarks:
    @pytest.fixture
    def sample_image_rgb(self):
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
            width, height,
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB
        )
        heif_img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
        plane = heif_img.get_plane(pylibheif.HeifChannel.Interleaved, True)
        np_plane = np.asarray(plane)
        np_plane[:] = img
        
        return heif_img

    @pytest.fixture
    def hevc_encoded_data(self, sample_image_rgb):
        """Pre-encode an image to test decoding speed"""
        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(50) # Fast preset
        encoder.encode_image(ctx, sample_image_rgb)
        return ctx.write_to_bytes()

    def test_benchmark_encode_hevc(self, benchmark, sample_image_rgb):
        """Benchmark HEVC encoding (1080p)"""
        def _encode():
            ctx = pylibheif.HeifContext()
            encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
            encoder.set_lossy_quality(80)
            encoder.encode_image(ctx, sample_image_rgb)
            return ctx
            
        benchmark(_encode)

    def test_benchmark_decode_hevc(self, benchmark, hevc_encoded_data):
        """Benchmark HEVC decoding (1080p)"""
        def _decode():
            ctx = pylibheif.HeifContext()
            ctx.read_from_memory(hevc_encoded_data)
            handle = ctx.get_primary_image_handle()
            return handle.decode(
                pylibheif.HeifColorspace.RGB,
                pylibheif.HeifChroma.InterleavedRGB
            )
            
        benchmark(_decode)

    def test_benchmark_encode_av1(self, benchmark, sample_image_rgb):
        """Benchmark AV1 encoding (1080p)"""
        def _encode():
            ctx = pylibheif.HeifContext()
            encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.AV1)
            # AV1 is slow, set lower quality/speed for benchmark
            encoder.set_lossy_quality(50) 
            encoder.encode_image(ctx, sample_image_rgb)
            return ctx
            
        benchmark(_encode)
