import os
import gc
import pytest
import pylibheif


def test_bytearray_lock_safety():
    # Load test image content
    image_path = os.path.join(os.path.dirname(__file__), "..", "images", "test.heic")
    assert os.path.exists(image_path), f"Test image not found at {image_path}"

    with open(image_path, "rb") as f:
        file_bytes = f.read()

    # Create a mutable bytearray
    data = bytearray(file_bytes)

    # Initialize context
    ctx = pylibheif.HeifContext()

    # Load from memory (zero-copy)
    ctx.read_from_memory(data)

    # Verify that trying to modify or resize the bytearray raises BufferError
    with pytest.raises(BufferError):
        data.extend(b"dummy")

    with pytest.raises(BufferError):
        data.clear()

    # Close the context
    ctx.close()

    # Verify that after closing the context, the bytearray lock is released
    # and we can modify/resize it without any errors
    data.extend(b"dummy")
    assert data[-5:] == b"dummy"
    data.clear()
    assert len(data) == 0


def test_bytearray_lock_gc_safety():
    # Load test image content
    image_path = os.path.join(os.path.dirname(__file__), "..", "images", "test.heic")
    with open(image_path, "rb") as f:
        file_bytes = f.read()

    data = bytearray(file_bytes)

    ctx = pylibheif.HeifContext()
    ctx.read_from_memory(data)

    # Verify lock is active
    with pytest.raises(BufferError):
        data.clear()

    # Delete context without explicit close, let GC handle it
    del ctx
    gc.collect()

    # Verify lock is released on garbage collection
    data.clear()
    assert len(data) == 0
