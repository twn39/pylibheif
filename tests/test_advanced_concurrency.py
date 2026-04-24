import pytest
import concurrent.futures
import numpy as np
import pylibheif


# Create a sample image to encode
def create_sample_array():
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    arr[:50, :50] = [255, 0, 0]
    return arr


@pytest.fixture(scope="session")
def sample_heic(tmp_path_factory):
    fn = str(tmp_path_factory.mktemp("data") / "test.heic")
    ctx = pylibheif.HeifContext()
    img = pylibheif.HeifImage.from_numpy(create_sample_array())
    enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    enc.encode_image(ctx, img)
    ctx.write_to_file(fn)
    return fn


def test_mixed_io_workload(sample_heic):
    """
    Test 1: Mixed encoding and decoding workload.
    Ensures libheif global state and GIL management handle concurrent read/write safely.
    """

    def task_decode():
        ctx = pylibheif.HeifContext()
        ctx.read_from_file(sample_heic)
        handle = ctx.get_primary_image_handle()
        img = handle.decode()
        arr = img.get_plane(pylibheif.HeifChannel.Interleaved, False)
        return np.asarray(arr).shape

    def task_encode():
        ctx = pylibheif.HeifContext()
        img = pylibheif.HeifImage.from_numpy(create_sample_array())
        enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        enc.encode_image(ctx, img)
        data = ctx.write_to_bytes()
        return len(data) > 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        # Submit 10 decodes and 10 encodes
        futures = []
        for _ in range(10):
            futures.append(executor.submit(task_decode))
            futures.append(executor.submit(task_encode))

        # Wait and verify
        results = [f.result() for f in futures]
        assert all(results), "Not all concurrent tasks succeeded"
        # Check specific decode shapes
        decode_results = [r for r in results if isinstance(r, tuple)]
        assert len(decode_results) == 10
        assert all(shape == (100, 100, 3) for shape in decode_results)


def test_concurrent_write_to_bytes():
    """
    Test 2: Concurrent write_to_bytes() on INDEPENDENT contexts.
    Verifies that the GIL release around memory estimation and writing works.
    """
    # Prepare 4 independent contexts
    contexts = []
    for _ in range(4):
        ctx = pylibheif.HeifContext()
        img = pylibheif.HeifImage.from_numpy(create_sample_array())
        enc = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
        enc.encode_image(ctx, img)
        contexts.append(ctx)

    def write_task(ctx):
        return len(ctx.write_to_bytes())

    # Run concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(write_task, ctx) for ctx in contexts]
        results = [f.result() for f in futures]

    assert len(results) == 4
    assert all(size > 0 for size in results)


def test_concurrent_encoder_creation():
    """
    Test 3: Concurrent HeifEncoder creation and descriptor querying.
    Verifies thread safety of our raw pointer caching and libheif's plugin registry.
    """

    def task_create_encoder():
        # Query descriptors concurrently
        descs = pylibheif.get_encoder_descriptors(pylibheif.HeifCompressionFormat.HEVC)
        if not descs:
            return False
        # Pick the first one and create an encoder
        try:
            enc = pylibheif.HeifEncoder(descs[0])
            name = enc.name
            return len(name) > 0
        except Exception as e:
            print(f"Failed to create encoder: {e}")
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(task_create_encoder) for _ in range(50)]
        results = [f.result() for f in futures]

    assert all(results), "Not all concurrent encoder creations succeeded"
