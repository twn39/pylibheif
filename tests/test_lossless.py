import pylibheif
import numpy as np


def test_lossless_encoding():
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    arr[:50, :50] = 255

    img = pylibheif.HeifImage.from_numpy(arr)
    ctx = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

    # Enable lossless
    enc.set_lossless(True)
    enc.encode_image(ctx, img)

    data = ctx.write_to_bytes()

    # Read back and compare exact pixels
    ctx_read = pylibheif.HeifContext()
    ctx_read.read_from_memory(data)
    handle = ctx_read.get_primary_image_handle()
    img_read = handle.decode(
        pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )

    plane = img_read.get_plane(pylibheif.HeifChannel.Interleaved, False)
    arr_out = np.asarray(plane)

    np.testing.assert_array_equal(arr, arr_out)
