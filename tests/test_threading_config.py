import os
import subprocess
import sys
import threading
import concurrent.futures
from PIL import Image
import pytest

import pylibheif
from pylibheif import (
    AsyncHeifContext,
    HeifColorspace,
    HeifChroma,
    HeifDecodingOptions,
    get_default_num_threads,
    set_default_num_threads,
    get_default_codec_executor,
    set_default_codec_executor,
    to_pillow,
)


@pytest.fixture
def sample_heic_path():
    path = os.path.join(os.path.dirname(__file__), "..", "images", "test.heic")
    return os.path.abspath(path)


def test_default_num_threads_getter_setter():
    """Test get_default_num_threads, set_default_num_threads, reset, and validation."""
    initial = get_default_num_threads()
    assert 1 <= initial <= 4, (
        f"Initial default threads should be in [1, 4], got {initial}"
    )

    try:
        set_default_num_threads(2)
        assert get_default_num_threads() == 2

        set_default_num_threads(6)
        assert get_default_num_threads() == 6

        # 0 resets to adaptive default
        set_default_num_threads(0)
        assert get_default_num_threads() == initial

        # Negative values must raise ValueError
        with pytest.raises(ValueError):
            set_default_num_threads(-1)
    finally:
        set_default_num_threads(0)


def test_env_var_override():
    """Test PYLIBHEIF_NUM_THREADS environment variable override in a clean subprocess."""
    code = "import pylibheif; print(pylibheif.get_default_num_threads())"
    env = os.environ.copy()
    env["PYLIBHEIF_NUM_THREADS"] = "3"

    res = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == "3"


def test_heif_decoding_options_kwargs():
    """Test HeifDecodingOptions keyword arguments constructor."""
    opts = HeifDecodingOptions(
        num_codec_threads=5,
        strict_decoding=True,
        ignore_transformations=True,
        convert_hdr_to_8bit=False,
    )
    assert opts.num_codec_threads == 5
    assert opts.strict_decoding is True
    assert opts.ignore_transformations is True
    assert opts.convert_hdr_to_8bit is False

    # Default constructor initializes num_codec_threads to current default
    cur_default = get_default_num_threads()
    default_opts = HeifDecodingOptions()
    assert default_opts.num_codec_threads == cur_default


def test_handle_decode_with_num_threads(sample_heic_path):
    """Test decoding with num_threads argument directly on HeifImageHandle."""
    ctx = pylibheif.HeifContext()
    ctx.read_from_file(sample_heic_path)
    handle = ctx.get_primary_image_handle()

    # Decode with explicit num_threads = 1
    img1 = handle.decode(num_threads=1)
    assert img1.width == handle.width
    assert img1.height == handle.height

    # Decode with explicit num_threads = 2
    img2 = handle.decode(num_threads=2)
    assert img2.width == handle.width
    assert img2.height == handle.height

    # Negative num_threads should raise ValueError
    with pytest.raises(ValueError):
        handle.decode(num_threads=-2)


def test_resolution_adaptive_small_image():
    """Test resolution-adaptive decoding for small image (<512x512)."""
    # Create small 64x64 test image
    ctx = pylibheif.HeifContext()
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    img_in = pylibheif.HeifImage(64, 64, HeifColorspace.RGB, HeifChroma.InterleavedRGB)
    img_in.add_plane(pylibheif.HeifChannel.Interleaved, 64, 64, 8)
    enc.encode_image(ctx, img_in)

    # Read back and decode without options (triggers adaptive small-image resolution path)
    data = ctx.write_to_bytes()
    ctx_in = pylibheif.HeifContext()
    ctx_in.read_from_memory(data)
    handle = ctx_in.get_primary_image_handle()

    assert handle.width == 64
    assert handle.height == 64
    decoded = handle.decode()
    assert decoded.width == 64
    assert decoded.height == 64


@pytest.mark.asyncio
async def test_async_decode_with_num_threads(sample_heic_path):
    """Test AsyncHeifImageHandle.decode with num_threads and verify dedicated thread pool."""
    thread_names = []

    def _record_thread():
        thread_names.append(threading.current_thread().name)

    async with await AsyncHeifContext.from_file(sample_heic_path) as ctx:
        handle = ctx.get_primary_image_handle()

        # Run async decode and record worker thread name
        img = await handle.decode(num_threads=2)
        assert img.width == handle.width

        # Also submit a task directly to the codec executor to verify prefix
        executor = get_default_codec_executor()
        future = executor.submit(_record_thread)
        future.result()

    assert len(thread_names) > 0
    assert thread_names[0].startswith("pylibheif-codec"), (
        f"Worker thread should start with 'pylibheif-codec', got {thread_names[0]}"
    )


def test_dedicated_codec_executor_management():
    """Test dedicated codec executor get, set, and shutdown."""
    executor = get_default_codec_executor()
    assert executor is not None

    custom_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=2, thread_name_prefix="custom-codec"
    )
    set_default_codec_executor(custom_executor)
    assert get_default_codec_executor() is custom_executor

    # Reset back
    set_default_codec_executor(None)
    # Lazy recreation on demand
    new_executor = get_default_codec_executor()
    assert new_executor is not custom_executor


def test_to_pillow_with_threads(sample_heic_path):
    """Test to_pillow integration with options and num_threads."""
    ctx = pylibheif.HeifContext()
    ctx.read_from_file(sample_heic_path)
    handle = ctx.get_primary_image_handle()

    # Pass num_threads to to_pillow
    im = to_pillow(handle, num_threads=2)
    assert isinstance(im, Image.Image)
    assert im.size == (handle.width, handle.height)

    # Pass custom options to to_pillow
    opts = HeifDecodingOptions(strict_decoding=True, num_codec_threads=1)
    im2 = to_pillow(handle, options=opts)
    assert isinstance(im2, Image.Image)
    assert im2.size == (handle.width, handle.height)


def test_pillow_image_open_with_num_threads_info(sample_heic_path):
    """Test Pillow Image.open with info['num_threads'] parameter."""
    pylibheif.register_pillow_opener()
    try:
        with Image.open(sample_heic_path) as im:
            im.info["num_threads"] = 2
            im.load()
            assert im.size[0] > 0
            assert im.size[1] > 0
    finally:
        pylibheif.unregister_pillow_opener()
