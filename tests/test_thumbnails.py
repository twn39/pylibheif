import os
import tempfile
import pytest
import numpy as np
import pylibheif


def create_gradient_image(width: int = 200, height: int = 200) -> pylibheif.HeifImage:
    img = pylibheif.HeifImage(
        width,
        height,
        pylibheif.HeifColorspace.RGB,
        pylibheif.HeifChroma.InterleavedRGB,
    )
    img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    arr = np.asarray(plane)
    # Generate RGB gradient
    for y in range(height):
        for x in range(width):
            arr[y, x] = [x % 256, y % 256, (x + y) % 256]
    return img


class TestThumbnailsSync:
    def test_encode_and_decode_thumbnail(self):
        img = create_gradient_image(200, 200)

        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        encoder.set_lossy_quality(80)

        master_handle = encoder.encode_image(ctx, img)
        assert master_handle is not None

        # Encode thumbnail with bbox_size 50
        thumb_handle = encoder.encode_thumbnail(ctx, img, master_handle, bbox_size=50)
        assert thumb_handle is not None
        assert max(thumb_handle.width, thumb_handle.height) <= 50

        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            ctx.write_to_file(tmp_path)
            assert os.path.getsize(tmp_path) > 0

            # Read back and verify thumbnail
            read_ctx = pylibheif.HeifContext()
            read_ctx.read_from_file(tmp_path)

            primary = read_ctx.get_primary_image_handle()
            assert primary.number_of_thumbnails == 1
            assert primary.get_number_of_thumbnails() == 1

            thumb_ids = primary.get_thumbnail_ids()
            assert len(thumb_ids) == 1
            thumb_id = thumb_ids[0]

            th = primary.get_thumbnail(thumb_id)
            assert max(th.width, th.height) <= 50

            # Test convenient property .thumbnails
            assert len(primary.thumbnails) == 1
            assert primary.thumbnails[0].width == th.width

            # Decode thumbnail image
            decoded_th = th.decode(
                pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
            )
            assert decoded_th.width == th.width
            assert decoded_th.height == th.height

            th_arr = np.asarray(decoded_th.get_plane(pylibheif.HeifChannel.Interleaved))
            assert th_arr.shape == (th.height, th.width, 3)
            assert th_arr.dtype == np.uint8
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_thumbnail_bbox_larger_than_image_returns_none(self):
        img = create_gradient_image(100, 100)

        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

        master_handle = encoder.encode_image(ctx, img)

        # When bbox_size >= image size, libheif does not generate a thumbnail and returns NULL
        thumb_handle = encoder.encode_thumbnail(ctx, img, master_handle, bbox_size=300)
        assert thumb_handle is None

    def test_assign_thumbnail(self):
        big_img = create_gradient_image(180, 180)
        small_img = create_gradient_image(40, 40)

        ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

        master_handle = encoder.encode_image(ctx, big_img)
        small_handle = encoder.encode_image(ctx, small_img)

        # Manually assign small_handle as thumbnail for master_handle
        ctx.assign_thumbnail(master_handle, small_handle)

        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            ctx.write_to_file(tmp_path)

            read_ctx = pylibheif.HeifContext()
            read_ctx.read_from_file(tmp_path)

            primary = read_ctx.get_primary_image_handle()
            assert primary.number_of_thumbnails == 1
            th = primary.thumbnails[0]
            assert th.width == 40
            assert th.height == 40
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestThumbnailsAsync:
    @pytest.mark.asyncio
    async def test_async_thumbnail_workflow(self):
        img = create_gradient_image(160, 160)

        async_ctx = pylibheif.AsyncHeifContext()
        async_encoder = pylibheif.AsyncHeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        async_encoder.set_lossy_quality(80)

        master_handle = await async_encoder.encode_image(async_ctx, img)
        assert master_handle is not None

        thumb_handle = await async_encoder.encode_thumbnail(
            async_ctx, img, master_handle, bbox_size=40
        )
        assert thumb_handle is not None
        assert max(thumb_handle.width, thumb_handle.height) <= 40

        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            await async_ctx.write_to_file(tmp_path)
            assert os.path.getsize(tmp_path) > 0

            read_ctx = await pylibheif.AsyncHeifContext.from_file(tmp_path)
            primary = read_ctx.get_primary_image_handle()
            assert primary.number_of_thumbnails == 1

            thumb_ids = primary.get_thumbnail_ids()
            assert len(thumb_ids) == 1

            th = await primary.get_thumbnail_async(thumb_ids[0])
            assert max(th.width, th.height) <= 40

            all_thumbs = await primary.get_thumbnails()
            assert len(all_thumbs) == 1
            assert all_thumbs[0].width == th.width

            decoded_th = await th.decode()
            assert decoded_th.width == th.width
            assert decoded_th.height == th.height
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_async_assign_thumbnail(self):
        big_img = create_gradient_image(120, 120)
        small_img = create_gradient_image(30, 30)

        async_ctx = pylibheif.AsyncHeifContext()
        async_encoder = pylibheif.AsyncHeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

        master_handle = await async_encoder.encode_image(async_ctx, big_img)
        small_handle = await async_encoder.encode_image(async_ctx, small_img)

        await async_ctx.assign_thumbnail_async(master_handle, small_handle)

        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            await async_ctx.write_to_file(tmp_path)

            read_ctx = await pylibheif.AsyncHeifContext.from_file(tmp_path)
            primary = read_ctx.get_primary_image_handle()
            assert primary.number_of_thumbnails == 1
            thumbs = await primary.get_thumbnails()
            assert thumbs[0].width == 30
            assert thumbs[0].height == 30
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
