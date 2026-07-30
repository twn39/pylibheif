import pathlib
import pytest
from pylibheif import HeifContext, AsyncHeifContext

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
SAMPLE_HEIC = PROJECT_ROOT / "images" / "test.heic"


def test_heif_context_explicit_reset():
    """Verify explicit HeifContext.reset()."""
    ctx = HeifContext()
    ctx.read_from_file(str(SAMPLE_HEIC))
    handle1 = ctx.get_primary_image_handle()
    assert handle1.width > 0

    ctx.reset()
    assert not ctx.is_closed

    # Re-read another buffer on the same context
    data = SAMPLE_HEIC.read_bytes()
    ctx.read_from_memory(data)
    handle2 = ctx.get_primary_image_handle()
    assert handle2.width > 0


def test_heif_context_auto_reset_on_reread():
    """Verify automatic context reset when re-reading without explicit reset call."""
    ctx = HeifContext()
    data = SAMPLE_HEIC.read_bytes()

    ctx.read_from_memory(data)
    h1 = ctx.get_primary_image_handle()

    # Reading again on same instance should safely auto-reset without raising error
    ctx.read_from_file(str(SAMPLE_HEIC))
    h2 = ctx.get_primary_image_handle()
    assert h2.width == h1.width


@pytest.mark.asyncio
async def test_async_heif_context_reset():
    """Verify AsyncHeifContext.reset()."""
    async with await AsyncHeifContext.from_file(str(SAMPLE_HEIC)) as ctx:
        h1 = ctx.get_primary_image_handle()
        assert h1.width > 0

        await ctx.reset()
        data = SAMPLE_HEIC.read_bytes()
        await ctx.read_from_memory(data)
        h2 = ctx.get_primary_image_handle()
        assert h2.width > 0
