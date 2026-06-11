import pytest
import pylibheif


def test_nclx_profile_roundtrip():
    # 1. Create a dummy image
    width = 64
    height = 64
    image = pylibheif.HeifImage(
        width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )
    image.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

    # Verify default profile type is NotPresent
    assert image.color_profile_type == pylibheif.HeifColorProfileType.NotPresent
    assert image.get_nclx_color_profile() is None

    # 2. Define and set an NCLX profile
    # Let's use BT.2020, PQ transfer characteristics, non-constant luminance matrix, and full range
    nclx = pylibheif.HeifColorProfileNclx(
        pylibheif.HeifColorPrimaries.ITU_R_BT_2020_2_and_2100_0,
        pylibheif.HeifTransferCharacteristics.ITU_R_BT_2100_0_PQ,
        pylibheif.HeifMatrixCoefficients.ITU_R_BT_2020_2_non_constant_luminance,
        True,
    )

    assert (
        nclx.color_primaries == pylibheif.HeifColorPrimaries.ITU_R_BT_2020_2_and_2100_0
    )
    assert (
        nclx.transfer_characteristics
        == pylibheif.HeifTransferCharacteristics.ITU_R_BT_2100_0_PQ
    )
    assert (
        nclx.matrix_coefficients
        == pylibheif.HeifMatrixCoefficients.ITU_R_BT_2020_2_non_constant_luminance
    )
    assert nclx.full_range_flag is True

    image.set_nclx_color_profile(nclx)

    # Verify updated profile on the image object
    assert image.color_profile_type == pylibheif.HeifColorProfileType.Nclx
    nclx_get = image.get_nclx_color_profile()
    assert nclx_get is not None
    assert (
        nclx_get.color_primaries
        == pylibheif.HeifColorPrimaries.ITU_R_BT_2020_2_and_2100_0
    )
    assert (
        nclx_get.transfer_characteristics
        == pylibheif.HeifTransferCharacteristics.ITU_R_BT_2100_0_PQ
    )
    assert (
        nclx_get.matrix_coefficients
        == pylibheif.HeifMatrixCoefficients.ITU_R_BT_2020_2_non_constant_luminance
    )
    assert nclx_get.full_range_flag is True

    # 3. Encode image and verify handle
    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    handle = encoder.encode_image(ctx, image)

    # Verify profile on the returned handle
    assert handle.color_profile_type == pylibheif.HeifColorProfileType.Nclx
    nclx_handle = handle.get_nclx_color_profile()
    assert nclx_handle is not None
    assert (
        nclx_handle.color_primaries
        == pylibheif.HeifColorPrimaries.ITU_R_BT_2020_2_and_2100_0
    )
    assert (
        nclx_handle.transfer_characteristics
        == pylibheif.HeifTransferCharacteristics.ITU_R_BT_2100_0_PQ
    )
    assert (
        nclx_handle.matrix_coefficients
        == pylibheif.HeifMatrixCoefficients.ITU_R_BT_2020_2_non_constant_luminance
    )
    assert nclx_handle.full_range_flag is True

    # Verify floats for primaries are readable (they are populated on decoding)
    assert isinstance(nclx_handle.color_primary_red_x, float)

    # 4. Write context and read it back
    data = ctx.write_to_bytes()
    ctx_new = pylibheif.HeifContext()
    ctx_new.read_from_memory(data)
    handle_new = ctx_new.get_primary_image_handle()

    assert handle_new.color_profile_type == pylibheif.HeifColorProfileType.Nclx
    nclx_new = handle_new.get_nclx_color_profile()
    assert nclx_new is not None
    assert (
        nclx_new.color_primaries
        == pylibheif.HeifColorPrimaries.ITU_R_BT_2020_2_and_2100_0
    )
    assert (
        nclx_new.transfer_characteristics
        == pylibheif.HeifTransferCharacteristics.ITU_R_BT_2100_0_PQ
    )
    assert (
        nclx_new.matrix_coefficients
        == pylibheif.HeifMatrixCoefficients.ITU_R_BT_2020_2_non_constant_luminance
    )
    assert nclx_new.full_range_flag is True


def test_raw_icc_profile_roundtrip():
    # 1. Create a dummy image
    width = 64
    height = 64
    image = pylibheif.HeifImage(
        width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )
    image.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

    assert image.get_raw_color_profile() == b""

    # 2. Set raw ICC profile
    dummy_icc = b"ICC_PROFILE_DUMMY_DATA_XYZ_1234567890_HELLO_WORLD"
    image.set_raw_color_profile("prof", dummy_icc)

    # Verify updated profile on the image object
    assert image.color_profile_type == pylibheif.HeifColorProfileType.Prof
    assert image.get_raw_color_profile() == dummy_icc

    # 3. Encode image and verify handle
    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    handle = encoder.encode_image(ctx, image)

    assert handle.color_profile_type == pylibheif.HeifColorProfileType.Prof
    assert handle.get_raw_color_profile() == dummy_icc

    # 4. Write context and read it back
    data = ctx.write_to_bytes()
    ctx_new = pylibheif.HeifContext()
    ctx_new.read_from_memory(data)
    handle_new = ctx_new.get_primary_image_handle()

    assert handle_new.color_profile_type == pylibheif.HeifColorProfileType.Prof
    assert handle_new.get_raw_color_profile() == dummy_icc


@pytest.mark.asyncio
async def test_async_color_profile():
    # 1. Create and write an image with NCLX profile
    width = 32
    height = 32
    image = pylibheif.HeifImage(
        width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )
    image.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)

    nclx = pylibheif.HeifColorProfileNclx(
        pylibheif.HeifColorPrimaries.ITU_R_BT_709_5,
        pylibheif.HeifTransferCharacteristics.ITU_R_BT_709_5,
        pylibheif.HeifMatrixCoefficients.ITU_R_BT_709_5,
        False,
    )
    image.set_nclx_color_profile(nclx)

    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    encoder.encode_image(ctx, image)
    data = ctx.write_to_bytes()

    # 2. Async read context and get async handle
    async_ctx = pylibheif.AsyncHeifContext()
    await async_ctx.read_from_memory(data)
    async_handle = async_ctx.get_primary_image_handle()

    # Verify color profile properties on AsyncHeifImageHandle
    assert async_handle.color_profile_type == pylibheif.HeifColorProfileType.Nclx

    nclx_profile = async_handle.get_nclx_color_profile()
    assert nclx_profile is not None
    assert nclx_profile.color_primaries == pylibheif.HeifColorPrimaries.ITU_R_BT_709_5
    assert (
        nclx_profile.transfer_characteristics
        == pylibheif.HeifTransferCharacteristics.ITU_R_BT_709_5
    )
    assert (
        nclx_profile.matrix_coefficients
        == pylibheif.HeifMatrixCoefficients.ITU_R_BT_709_5
    )
    assert nclx_profile.full_range_flag is False

    assert async_handle.get_raw_color_profile() == b""
