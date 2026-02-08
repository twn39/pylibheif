import pytest
import pylibheif
import numpy as np


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
            width,
            height,
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB,
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
        encoder.set_lossy_quality(50)  # Fast preset
        encoder.encode_image(ctx, sample_image_rgb)
        return ctx.write_to_bytes()

    def test_benchmark_encode_hevc(self, benchmark, sample_image_rgb):
        """Benchmark HEVC encoding (1080p) - x265"""

        def _encode():
            ctx = pylibheif.HeifContext()
            encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
            encoder.set_lossy_quality(80)  # Realistic quality
            # Use medium (default) for realistic testing
            encoder.encode_image(ctx, sample_image_rgb, preset="medium")
            return ctx

        benchmark(_encode)

    def test_benchmark_decode_hevc(self, benchmark, hevc_encoded_data):
        """Benchmark HEVC decoding (1080p)"""

        def _decode():
            ctx = pylibheif.HeifContext()
            ctx.read_from_memory(hevc_encoded_data)
            handle = ctx.get_primary_image_handle()
            return handle.decode(
                pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
            )

        benchmark(_decode)

    def test_benchmark_encode_av1(self, benchmark, sample_image_rgb):
        """Benchmark AV1 encoding (1080p) - AOM"""

        def _encode():
            ctx = pylibheif.HeifContext()
            encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.AV1)
            encoder.set_lossy_quality(86)  # Iso-quality match to x265 Q80
            # Set speed 6 (Default/Balanced tier)
            encoder.set_parameter("speed", "6")
            encoder.encode_image(ctx, sample_image_rgb)
            return ctx

        benchmark(_encode)

    def test_benchmark_decode_hevc_pillow(self, benchmark, hevc_encoded_data):
        """Benchmark HEVC decoding with pillow-heif"""
        import pillow_heif
        import io

        def _decode():
            # pillow-heif can read from bytes/bio
            heif_file = pillow_heif.open_heif(io.BytesIO(hevc_encoded_data))
            # Accessing data triggers decode
            return np.asarray(heif_file)

        benchmark(_decode)

    def test_benchmark_encode_hevc_pillow(self, benchmark, sample_image_rgb):
        """Benchmark HEVC encoding with pillow-heif"""
        import pillow_heif
        from PIL import Image
        import io

        pillow_heif.register_heif_opener()

        # Convert pylibheif image back to numpy for PIL
        plane = sample_image_rgb.get_plane(pylibheif.HeifChannel.Interleaved, False)
        arr = np.asarray(plane)
        pil_img = Image.fromarray(arr)

        # Pre-create BytesIO to avoid object creation overhead in loop (optional, but good for pure encoding test)
        # However, save() requires a file-like object.
        # Since we want to benchmark encoding, including IO writes is fair as long as it's memory.

        def _encode():
            bio = io.BytesIO()
            # pillow-heif uses x265 by default.
            # We try to match quality=80.
            # pillow-heif encoding speed preset handling:
            # It maps 'enc_params' to x265 params. 'preset': 'medium'
            pil_img.save(
                bio, format="HEIF", quality=80, enc_params={"preset": "medium"}
            )
            return bio.getvalue()

        benchmark(_encode)

    def test_benchmark_encode_kvazaar(self, benchmark, sample_image_rgb):
        """Benchmark Kvazaar encoding (1080p)"""
        import pylibheif

        # Find Kvazaar encoder
        descriptors = pylibheif.get_encoder_descriptors()
        kvazaar_desc = next((d for d in descriptors if "kvazaar" in d.id_name), None)

        if not kvazaar_desc:
            pytest.skip("Kvazaar encoder not available")

        def _encode():
            ctx = pylibheif.HeifContext()
            encoder = pylibheif.HeifEncoder(kvazaar_desc)
            encoder.set_lossy_quality(80)  # Realistic quality
            # Kvazaar settings: Default (as no preset support via libheif yet)
            encoder.encode_image(ctx, sample_image_rgb)
            return ctx

        benchmark(_encode)
