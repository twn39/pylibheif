import pytest
import pylibheif
import numpy as np


# Helper to create a dummy image
def create_dummy_image(width=64, height=64):
    img = pylibheif.HeifImage(
        width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )
    img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    data = np.asarray(plane)
    data[:] = 128  # Grey
    return img


@pytest.mark.asyncio
class TestAsyncHeif:
    async def test_async_context_read_write(self, tmp_path):
        # Create a real HEIC file first using synchronous API
        img = create_dummy_image()
        ctx_sync = pylibheif.HeifContext()
        enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        enc.encode_image(ctx_sync, img)
        input_file = tmp_path / "input.heic"
        ctx_sync.write_to_file(str(input_file))

        # Now test Async API
        ctx = pylibheif.AsyncHeifContext()
        await ctx.read_from_file(str(input_file))

        # Test get handles
        handle = ctx.get_primary_image_handle()
        assert isinstance(handle, pylibheif.AsyncHeifImageHandle)
        assert handle.width == 64
        assert handle.height == 64

        # Test async decode
        decoded_img = await handle.decode()
        assert decoded_img.get_width(pylibheif.HeifChannel.Interleaved) == 64
        assert decoded_img.get_height(pylibheif.HeifChannel.Interleaved) == 64

        # Test async encode
        new_ctx = pylibheif.AsyncHeifContext()
        encoder = pylibheif.AsyncHeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(50)

        await encoder.encode_image(new_ctx, decoded_img)

        # Test async write
        output_file = tmp_path / "output.heic"
        await new_ctx.write_to_file(str(output_file))

        assert output_file.exists()
        assert output_file.stat().st_size > 0

    async def test_async_read_from_memory(self):
        # Create bytes
        img = create_dummy_image()
        ctx_sync = pylibheif.HeifContext()
        enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        enc.encode_image(ctx_sync, img)
        data = ctx_sync.write_to_bytes()

        ctx = pylibheif.AsyncHeifContext()
        await ctx.read_from_memory(data)

        handle = ctx.get_primary_image_handle()
        assert handle.width == 64

    async def test_async_write_to_bytes(self):
        img = create_dummy_image()
        ctx = pylibheif.AsyncHeifContext()
        encoder = pylibheif.AsyncHeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

        await encoder.encode_image(ctx, img)
        data = await ctx.write_to_bytes()

        assert len(data) > 0
        assert data.startswith(b"\x00\x00\x00")  # ftyp box usually starts with size

    async def test_async_context_manager(self):
        async with pylibheif.AsyncHeifContext() as ctx:
            assert isinstance(ctx, pylibheif.AsyncHeifContext)
            # Should be able to call async methods
            img = create_dummy_image()
            encoder = pylibheif.AsyncHeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
            await encoder.encode_image(ctx, img)
            data = await ctx.write_to_bytes()
            assert len(data) > 0
