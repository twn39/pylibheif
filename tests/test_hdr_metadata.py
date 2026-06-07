"""
Tests for HDR Metadata (CLLI, MDCV, AMVE) API.
"""

import pytest
import numpy as np
import pylibheif


def test_metadata_struct_init():
    # HeifContentLightLevel
    cll = pylibheif.HeifContentLightLevel(max_content_light_level=1000, max_pic_average_light_level=400)
    assert cll.max_content_light_level == 1000
    assert cll.max_pic_average_light_level == 400

    # Default init
    cll_default = pylibheif.HeifContentLightLevel()
    assert cll_default.max_content_light_level == 0
    assert cll_default.max_pic_average_light_level == 0

    # HeifMasteringDisplayColourVolume
    mdcv = pylibheif.HeifMasteringDisplayColourVolume(
        red_primary=(0.680, 0.320),
        green_primary=(0.265, 0.690),
        blue_primary=(0.150, 0.060),
        white_point=(0.3127, 0.3290),
        max_luminance=1000.0,
        min_luminance=0.005
    )
    assert pytest.approx(mdcv.red_primary[0], abs=1e-6) == 0.680
    assert pytest.approx(mdcv.red_primary[1], abs=1e-6) == 0.320
    assert pytest.approx(mdcv.green_primary[0], abs=1e-6) == 0.265
    assert pytest.approx(mdcv.green_primary[1], abs=1e-6) == 0.690
    assert pytest.approx(mdcv.blue_primary[0], abs=1e-6) == 0.150
    assert pytest.approx(mdcv.blue_primary[1], abs=1e-6) == 0.060
    assert pytest.approx(mdcv.white_point[0], abs=1e-6) == 0.3127
    assert pytest.approx(mdcv.white_point[1], abs=1e-6) == 0.3290
    assert mdcv.max_luminance == 1000.0
    assert mdcv.min_luminance == 0.005

    # HeifAmbientViewingEnvironment
    amve = pylibheif.HeifAmbientViewingEnvironment(
        ambient_illumination=314.15,
        ambient_light=(0.3127, 0.3290)
    )
    assert amve.ambient_illumination == 314.15
    assert pytest.approx(amve.ambient_light[0], abs=1e-6) == 0.3127
    assert pytest.approx(amve.ambient_light[1], abs=1e-6) == 0.3290


def test_image_metadata_get_set():
    width, height = 64, 64
    img = pylibheif.HeifImage(width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB)
    
    # 1. Verify default state (no metadata)
    assert not img.has_content_light_level
    assert not img.has_mastering_display_colour_volume
    assert not img.has_ambient_viewing_environment
    
    assert img.content_light_level is None
    assert img.mastering_display_colour_volume is None
    assert img.ambient_viewing_environment is None

    # 2. Content Light Level (CLLI)
    cll = pylibheif.HeifContentLightLevel(1000, 400)
    img.content_light_level = cll
    assert img.has_content_light_level
    ret_cll = img.content_light_level
    assert ret_cll is not None
    assert ret_cll.max_content_light_level == 1000
    assert ret_cll.max_pic_average_light_level == 400

    # 3. Mastering Display Colour Volume (MDCV)
    mdcv = pylibheif.HeifMasteringDisplayColourVolume(
        red_primary=(0.680, 0.320),
        green_primary=(0.265, 0.690),
        blue_primary=(0.150, 0.060),
        white_point=(0.3127, 0.3290),
        max_luminance=1000.0,
        min_luminance=0.005
    )
    img.mastering_display_colour_volume = mdcv
    assert img.has_mastering_display_colour_volume
    ret_mdcv = img.mastering_display_colour_volume
    assert ret_mdcv is not None
    # Verify floats with a small tolerance due to 1/50000.0f fixed point precision
    assert pytest.approx(ret_mdcv.red_primary[0], abs=1e-4) == 0.680
    assert pytest.approx(ret_mdcv.red_primary[1], abs=1e-4) == 0.320
    assert pytest.approx(ret_mdcv.green_primary[0], abs=1e-4) == 0.265
    assert pytest.approx(ret_mdcv.green_primary[1], abs=1e-4) == 0.690
    assert pytest.approx(ret_mdcv.blue_primary[0], abs=1e-4) == 0.150
    assert pytest.approx(ret_mdcv.blue_primary[1], abs=1e-4) == 0.060
    assert pytest.approx(ret_mdcv.white_point[0], abs=1e-4) == 0.3127
    assert pytest.approx(ret_mdcv.white_point[1], abs=1e-4) == 0.3290
    # Luminance has 1/10000.0 precision
    assert pytest.approx(ret_mdcv.max_luminance, abs=1e-3) == 1000.0
    assert pytest.approx(ret_mdcv.min_luminance, abs=1e-4) == 0.005

    # 4. Ambient Viewing Environment (AMVE)
    amve = pylibheif.HeifAmbientViewingEnvironment(
        ambient_illumination=315.5,
        ambient_light=(0.3127, 0.3290)
    )
    img.ambient_viewing_environment = amve
    assert img.has_ambient_viewing_environment
    ret_amve = img.ambient_viewing_environment
    assert ret_amve is not None
    assert pytest.approx(ret_amve.ambient_illumination, abs=1e-3) == 315.5
    assert pytest.approx(ret_amve.ambient_light[0], abs=1e-4) == 0.3127
    assert pytest.approx(ret_amve.ambient_light[1], abs=1e-4) == 0.3290


def test_hdr_metadata_roundtrip():
    # Create an image and set HDR metadata
    width, height = 64, 64
    img = pylibheif.HeifImage(width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB)
    img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    arr = np.asarray(plane)
    arr[:] = 128  # Grey block

    cll = pylibheif.HeifContentLightLevel(1200, 600)
    mdcv = pylibheif.HeifMasteringDisplayColourVolume(
        red_primary=(0.680, 0.320),
        green_primary=(0.265, 0.690),
        blue_primary=(0.150, 0.060),
        white_point=(0.3127, 0.3290),
        max_luminance=1000.0,
        min_luminance=0.005
    )
    amve = pylibheif.HeifAmbientViewingEnvironment(
        ambient_illumination=314.0,
        ambient_light=(0.3127, 0.3290)
    )

    img.content_light_level = cll
    img.mastering_display_colour_volume = mdcv
    img.ambient_viewing_environment = amve

    # Encode the image
    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    encoder.encode_image(ctx, img)

    # Write to memory bytes
    data = ctx.write_to_bytes()
    assert len(data) > 0

    # Read back the image
    ctx2 = pylibheif.HeifContext()
    ctx2.read_from_memory(data)
    handle = ctx2.get_primary_image_handle()

    # 1. Verify on handle
    assert handle.has_content_light_level
    assert handle.has_mastering_display_colour_volume
    assert handle.has_ambient_viewing_environment

    h_cll = handle.content_light_level
    assert h_cll is not None
    assert h_cll.max_content_light_level == 1200
    assert h_cll.max_pic_average_light_level == 600

    h_mdcv = handle.mastering_display_colour_volume
    assert h_mdcv is not None
    assert pytest.approx(h_mdcv.red_primary[0], abs=1e-4) == 0.680
    assert pytest.approx(h_mdcv.red_primary[1], abs=1e-4) == 0.320
    assert pytest.approx(h_mdcv.green_primary[0], abs=1e-4) == 0.265
    assert pytest.approx(h_mdcv.green_primary[1], abs=1e-4) == 0.690
    assert pytest.approx(h_mdcv.blue_primary[0], abs=1e-4) == 0.150
    assert pytest.approx(h_mdcv.blue_primary[1], abs=1e-4) == 0.060
    assert pytest.approx(h_mdcv.white_point[0], abs=1e-4) == 0.3127
    assert pytest.approx(h_mdcv.white_point[1], abs=1e-4) == 0.3290
    assert pytest.approx(h_mdcv.max_luminance, abs=1e-3) == 1000.0
    assert pytest.approx(h_mdcv.min_luminance, abs=1e-4) == 0.005

    h_amve = handle.ambient_viewing_environment
    assert h_amve is not None
    assert pytest.approx(h_amve.ambient_illumination, abs=1e-3) == 314.0
    assert pytest.approx(h_amve.ambient_light[0], abs=1e-4) == 0.3127
    assert pytest.approx(h_amve.ambient_light[1], abs=1e-4) == 0.3290

    # 2. Verify on decoded image
    decoded_img = handle.decode()
    assert decoded_img.has_content_light_level
    assert decoded_img.has_mastering_display_colour_volume
    assert decoded_img.has_ambient_viewing_environment

    img_cll = decoded_img.content_light_level
    assert img_cll.max_content_light_level == 1200
    assert img_cll.max_pic_average_light_level == 600


@pytest.mark.asyncio
async def test_async_hdr_metadata():
    # Read/write via Async wrapper
    width, height = 64, 64
    img = pylibheif.HeifImage(width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB)
    img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    
    cll = pylibheif.HeifContentLightLevel(800, 300)
    img.content_light_level = cll

    ctx = pylibheif.AsyncHeifContext()
    encoder = pylibheif.AsyncHeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    await encoder.encode_image(ctx, img)
    
    data = await ctx.write_to_bytes()
    
    # Read back async
    ctx2 = pylibheif.AsyncHeifContext()
    await ctx2.read_from_memory(data)
    handle = ctx2.get_primary_image_handle()
    
    assert handle.has_content_light_level
    h_cll = handle.content_light_level
    assert h_cll is not None
    assert h_cll.max_content_light_level == 800
    assert h_cll.max_pic_average_light_level == 300
