import os
import pytest
import pylibheif


@pytest.fixture
def heic_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "images", "test.heic")
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
    return path


def test_encoding_options_getters_setters():
    opts = pylibheif.HeifEncodingOptions()

    # Test save_alpha_channel
    opts.save_alpha_channel = False
    assert opts.save_alpha_channel is False
    opts.save_alpha_channel = True
    assert opts.save_alpha_channel is True

    # Test save_two_colr_boxes_when_ICC_and_nclx_available
    opts.save_two_colr_boxes_when_ICC_and_nclx_available = True
    assert opts.save_two_colr_boxes_when_ICC_and_nclx_available is True
    opts.save_two_colr_boxes_when_ICC_and_nclx_available = False
    assert opts.save_two_colr_boxes_when_ICC_and_nclx_available is False

    # Test macOS_compatibility_workaround_no_nclx_profile
    opts.macOS_compatibility_workaround_no_nclx_profile = True
    assert opts.macOS_compatibility_workaround_no_nclx_profile is True
    opts.macOS_compatibility_workaround_no_nclx_profile = False
    assert opts.macOS_compatibility_workaround_no_nclx_profile is False

    # Test image_orientation
    opts.image_orientation = pylibheif.HeifOrientation.Rotate90Cw
    assert opts.image_orientation == pylibheif.HeifOrientation.Rotate90Cw
    opts.image_orientation = pylibheif.HeifOrientation.Normal
    assert opts.image_orientation == pylibheif.HeifOrientation.Normal

    # Test prefer_uncC_short_form
    opts.prefer_uncC_short_form = False
    assert opts.prefer_uncC_short_form is False
    opts.prefer_uncC_short_form = True
    assert opts.prefer_uncC_short_form is True

    # Test preferred_chroma_downsampling_algorithm
    opts.preferred_chroma_downsampling_algorithm = (
        pylibheif.HeifChromaDownsamplingAlgorithm.SharpYuv
    )
    assert (
        opts.preferred_chroma_downsampling_algorithm
        == pylibheif.HeifChromaDownsamplingAlgorithm.SharpYuv
    )

    # Test preferred_chroma_upsampling_algorithm
    opts.preferred_chroma_upsampling_algorithm = (
        pylibheif.HeifChromaUpsamplingAlgorithm.NearestNeighbor
    )
    assert (
        opts.preferred_chroma_upsampling_algorithm
        == pylibheif.HeifChromaUpsamplingAlgorithm.NearestNeighbor
    )

    # Test only_use_preferred_chroma_algorithm
    opts.only_use_preferred_chroma_algorithm = True
    assert opts.only_use_preferred_chroma_algorithm is True
    opts.only_use_preferred_chroma_algorithm = False
    assert opts.only_use_preferred_chroma_algorithm is False


def test_encode_with_options(heic_path):
    # Load an image
    ctx = pylibheif.HeifContext()
    ctx.read_from_file(heic_path)
    handle = ctx.get_primary_image_handle()
    image = handle.decode(
        pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )

    # Create encoder
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)

    # Create and configure encoding options
    opts = pylibheif.HeifEncodingOptions()
    opts.save_alpha_channel = False
    opts.image_orientation = pylibheif.HeifOrientation.Rotate90Cw
    opts.preferred_chroma_downsampling_algorithm = (
        pylibheif.HeifChromaDownsamplingAlgorithm.SharpYuv
    )

    # Encode with options
    write_ctx = pylibheif.HeifContext()
    out_handle = encoder.encode_image(write_ctx, image, options=opts)

    assert out_handle is not None
    # Verify the output can be written and read back
    data = write_ctx.write_to_bytes()
    assert len(data) > 0


@pytest.mark.asyncio
async def test_async_encode_with_options(heic_path):
    ctx = pylibheif.AsyncHeifContext()
    await ctx.read_from_file(heic_path)
    handle = ctx.get_primary_image_handle()
    image = await handle.decode(
        pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )

    encoder = pylibheif.AsyncHeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    opts = pylibheif.HeifEncodingOptions()
    opts.save_alpha_channel = False
    opts.image_orientation = pylibheif.HeifOrientation.Rotate270Cw

    write_ctx = pylibheif.AsyncHeifContext()
    out_handle = await encoder.encode_image(write_ctx, image, options=opts)
    assert out_handle is not None
    data = await write_ctx.write_to_bytes()
    assert len(data) > 0
