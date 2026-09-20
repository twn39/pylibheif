import io
import pytest
import numpy as np
import pylibheif


@pytest.fixture(scope="module")
def sample_image_1080p():
    """Generate a synthetic 1080p test image."""
    width, height = 1920, 1080
    img = pylibheif.HeifImage(
        width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )
    img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    np_plane = np.asarray(plane)
    np_plane[:, :, 0] = 120
    np_plane[:, :, 1] = 180
    np_plane[:, :, 2] = 240
    return img


@pytest.fixture(scope="module")
def sample_heif_bytes(sample_image_1080p):
    """Encode 1080p image into raw HEIF bytes for reading benchmarks."""
    ctx = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    enc.set_lossy_quality(80)
    enc.encode_image(ctx, sample_image_1080p)
    return ctx.write_to_bytes()


def test_benchmark_stream_write_batch_calls(sample_image_1080p):
    """Verify that writing a 1080p encoded context produces minimal write() calls."""
    ctx = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    enc.set_lossy_quality(80)
    enc.encode_image(ctx, sample_image_1080p)

    class CountingStream(io.BytesIO):
        def __init__(self):
            super().__init__()
            self.write_count = 0

        def write(self, b):
            self.write_count += 1
            return super().write(b)

    out = CountingStream()
    ctx.write_to_stream(out)

    assert out.tell() > 1000
    # Before buffering, libheif invoked write hundreds of times.
    # With 64KB buffering, calls must be under 10.
    assert out.write_count <= 10, f"Expected <= 10 write calls, got {out.write_count}"


def test_benchmark_stream_write_performance(benchmark, sample_image_1080p):
    """Benchmark write_to_stream throughput with 64KB buffering."""
    ctx = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    enc.set_lossy_quality(80)
    enc.encode_image(ctx, sample_image_1080p)

    def _do_write():
        bio = io.BytesIO()
        ctx.write_to_stream(bio)
        return bio.tell()

    benchmark(_do_write)


def test_benchmark_stream_read_performance(benchmark, sample_heif_bytes):
    """Benchmark read_from_stream with zero-copy readinto and redundant seek elimination."""

    def _do_read():
        bio = io.BytesIO(sample_heif_bytes)
        ctx = pylibheif.HeifContext()
        ctx.read_from_stream(bio)
        handle = ctx.get_primary_image_handle()
        return handle.width

    benchmark(_do_read)
