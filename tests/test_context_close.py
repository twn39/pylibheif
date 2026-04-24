import pytest
import pylibheif
import os


@pytest.fixture
def heic_path():
    """返回测试 HEIC 文件路径"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "images", "test.heic")
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
    return path


def test_context_close(heic_path):
    ctx = pylibheif.HeifContext()
    ctx.read_from_file(heic_path)
    handle = ctx.get_primary_image_handle()
    assert handle.width > 0

    ctx.close()
    with pytest.raises(RuntimeError, match="HeifContext has been closed"):
        ctx.get_primary_image_handle()


def test_context_with_statement(heic_path):
    with pylibheif.HeifContext() as ctx:
        ctx.read_from_file(heic_path)
        handle = ctx.get_primary_image_handle()
        assert handle.width > 0

    with pytest.raises(RuntimeError, match="HeifContext has been closed"):
        ctx.get_primary_image_handle()


@pytest.mark.asyncio
async def test_async_context_close(heic_path):
    ctx = pylibheif.AsyncHeifContext()
    await ctx.read_from_file(heic_path)
    handle = ctx.get_primary_image_handle()
    assert handle.width > 0

    ctx.close()
    with pytest.raises(RuntimeError, match="HeifContext has been closed"):
        ctx.get_primary_image_handle()


@pytest.mark.asyncio
async def test_async_context_with_statement(heic_path):
    async with pylibheif.AsyncHeifContext() as ctx:
        await ctx.read_from_file(heic_path)
        handle = ctx.get_primary_image_handle()
        assert handle.width > 0

    with pytest.raises(RuntimeError, match="HeifContext has been closed"):
        ctx.get_primary_image_handle()
