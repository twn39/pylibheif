import io
import pytest
from PIL import Image

from pylibheif import (
    HeifContext,
    HeifImage,
    HeifEncoder,
    HeifTrackType,
    HeifCompressionFormat,
    AsyncHeifContext,
    register_pillow_opener,
)


@pytest.fixture(autouse=True)
def setup_pillow():
    register_pillow_opener()


def _create_rgb_image(width: int, height: int, color: tuple[int, int, int], duration: int = 100) -> HeifImage:
    pil_img = Image.new("RGB", (width, height), color)
    img = HeifImage.from_pillow(pil_img)
    img.duration = duration
    return img


def _create_rgba_image(width: int, height: int, color: tuple[int, int, int, int], duration: int = 100) -> HeifImage:
    pil_img = Image.new("RGBA", (width, height), color)
    img = HeifImage.from_pillow(pil_img)
    img.duration = duration
    return img


def test_heif_track_basic_encoding_and_decoding():
    """Test creating a visual sequence track, encoding frames, and decoding them back."""
    width, height = 64, 64
    ctx = HeifContext()
    ctx.set_sequence_timescale(1000)
    ctx.set_number_of_sequence_repetitions(0)  # infinite loop
    ctx.set_major_brand("avis")
    ctx.add_compatible_brand("avis")
    ctx.add_compatible_brand("mif1")

    track = ctx.add_visual_sequence_track(width, height, HeifTrackType.ImageSequence, 1000)
    assert track.id > 0

    encoder = HeifEncoder(HeifCompressionFormat.AV1)

    colors = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
    ]
    durations = [100, 200, 300]

    for color, dur in zip(colors, durations):
        img = _create_rgb_image(width, height, color, duration=dur)
        track.encode_sequence_image(img, encoder, save_alpha=False)

    track.encode_end_of_sequence(encoder)

    # Export to memory
    data = ctx.write_to_bytes()
    assert len(data) > 0
    ctx.close()

    # Read back and inspect
    read_ctx = HeifContext()
    read_ctx.read_from_memory(data)
    assert read_ctx.has_sequence() is True
    assert read_ctx.get_number_of_sequence_tracks() >= 1

    read_track = read_ctx.get_track(0)
    assert read_track.id > 0
    res = read_track.resolution
    assert res == (width, height)
    assert read_track.timescale == 1000
    assert read_track.track_type == HeifTrackType.ImageSequence.value

    # Decode frames sequentially
    decoded_frames = []
    decoded_durations = []
    while True:
        frame = read_track.decode_next_image()
        if frame is None:
            break
        decoded_frames.append(frame)
        decoded_durations.append(frame.duration)

    assert len(decoded_frames) == 3
    assert decoded_durations == [100, 200, 300]
    read_ctx.close()


def test_infinite_loop_prevention_on_decode():
    """Verify that looping animations do not cause decode_next_image to loop infinitely."""
    width, height = 32, 32
    ctx = HeifContext()
    ctx.set_sequence_timescale(600)
    ctx.set_number_of_sequence_repetitions(0)  # Looping animation
    track = ctx.add_visual_sequence_track(width, height, HeifTrackType.ImageSequence, 600)
    encoder = HeifEncoder(HeifCompressionFormat.AV1)

    for _ in range(2):
        img = _create_rgb_image(width, height, (128, 128, 128), duration=50)
        track.encode_sequence_image(img, encoder)
    track.encode_end_of_sequence(encoder)

    data = ctx.write_to_bytes()
    ctx.close()

    read_ctx = HeifContext()
    read_ctx.read_from_memory(data)
    read_track = read_ctx.get_track(0)

    # Safe decoding with default ignore_sequence_editlist=True should yield exactly 2 frames
    frames = []
    while True:
        f = read_track.decode_next_image()
        if f is None:
            break
        frames.append(f)
        if len(frames) > 10:
            pytest.fail("Infinite decode loop detected! CVE-2026-62377 defense failed.")

    assert len(frames) == 2
    read_ctx.close()


@pytest.mark.asyncio
async def test_async_sequence_track_workflow():
    """Test async track workflow with AsyncHeifContext and AsyncHeifTrack."""
    width, height = 48, 48
    ctx = AsyncHeifContext()
    ctx.set_sequence_timescale(1000)

    track = await ctx.add_visual_sequence_track_async(width, height, HeifTrackType.ImageSequence, 1000)
    encoder = HeifEncoder(HeifCompressionFormat.AV1)

    for c in [(200, 10, 10), (10, 200, 10)]:
        img = _create_rgb_image(width, height, c, duration=150)
        await track.encode_sequence_image_async(img, encoder)

    await track.encode_end_of_sequence_async(encoder)

    data = await ctx.write_to_bytes()
    assert len(data) > 0

    read_ctx = await AsyncHeifContext.from_memory(data)
    assert read_ctx.has_sequence is True
    read_track = await read_ctx.get_track_async(0)
    assert read_track.resolution == (width, height)

    f1 = await read_track.decode_next_image_async()
    assert f1 is not None
    assert f1.duration == 150

    f2 = await read_track.decode_next_image_async()
    assert f2 is not None
    assert f2.duration == 150

    f3 = await read_track.decode_next_image_async()
    assert f3 is None


def test_pillow_animated_avif_roundtrip():
    """Test Pillow save_all=True writing animated AVIF (avis) and reading it back."""
    frames = [
        Image.new("RGB", (64, 64), color=(255, 0, 0)),
        Image.new("RGB", (64, 64), color=(0, 255, 0)),
        Image.new("RGB", (64, 64), color=(0, 0, 255)),
    ]

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="AVIF",
        save_all=True,
        append_images=frames[1:],
        duration=[100, 150, 200],
        loop=0,
    )
    data = buf.getvalue()
    assert len(data) > 0

    # Inspect container brand
    assert b"avis" in data[:32]

    # Read back with Pillow
    buf.seek(0)
    im = Image.open(buf)
    assert getattr(im, "is_animated", False) is True
    assert getattr(im, "n_frames", 1) == 3
    assert im.tell() == 0
    assert im.info["loop"] == 0
    assert im.info["duration"] == 100

    # Check frame 0 pixel
    im.load()
    p0 = im.getpixel((10, 10))
    assert isinstance(p0, tuple)
    assert abs(p0[0] - 255) < 15 and p0[1] < 15 and p0[2] < 15

    # Seek to frame 1
    im.seek(1)
    assert im.tell() == 1
    assert im.info["duration"] == 150
    im.load()
    p1 = im.getpixel((10, 10))
    assert isinstance(p1, tuple)
    assert p1[0] < 15 and abs(p1[1] - 255) < 15 and p1[2] < 15

    # Seek to frame 2
    im.seek(2)
    assert im.tell() == 2
    assert im.info["duration"] == 200
    im.load()
    p2 = im.getpixel((10, 10))
    assert isinstance(p2, tuple)
    assert p2[0] < 15 and p2[1] < 15 and abs(p2[2] - 255) < 15

    # Seek back to frame 0
    im.seek(0)
    assert im.tell() == 0
    im.load()
    p0_again = im.getpixel((10, 10))
    assert isinstance(p0_again, tuple)
    assert abs(p0_again[0] - 255) < 15

    # Seek out of bounds raises EOFError
    with pytest.raises(EOFError):
        im.seek(3)

    im.close()


def test_pillow_animated_rgba_avif():
    """Test animated AVIF with alpha channel preservation."""
    frames = [
        Image.new("RGBA", (32, 32), color=(255, 0, 0, 128)),
        Image.new("RGBA", (32, 32), color=(0, 255, 0, 64)),
    ]

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="AVIF",
        save_all=True,
        append_images=[frames[1]],
        duration=80,
    )
    buf.seek(0)

    im = Image.open(buf)
    assert getattr(im, "is_animated", False) is True
    assert getattr(im, "n_frames", 1) == 2
    assert im.mode == "RGBA"

    im.seek(0)
    im.load()
    p0 = im.getpixel((5, 5))
    assert isinstance(p0, tuple)
    assert p0[3] > 0  # Alpha channel is preserved

    im.close()


def test_non_sequence_file_safety():
    """Ensure static single-frame files are not mistakenly marked as animated."""
    img = Image.new("RGB", (32, 32), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="AVIF")
    buf.seek(0)

    read_ctx = HeifContext()
    read_ctx.read_from_memory(buf.getvalue())
    assert read_ctx.has_sequence() is False
    assert read_ctx.get_number_of_sequence_tracks() == 0
    read_ctx.close()

    buf.seek(0)
    pil_img = Image.open(buf)
    assert getattr(pil_img, "is_animated", False) is False
    assert getattr(pil_img, "n_frames", 1) == 1
    pil_img.close()
