import pytest
from pylibheif import (
    AsyncHeifContext,
    ConcurrencyBudget,
    HeifCompressionFormat,
    HeifContext,
    HeifEncoder,
    get_concurrency_budget,
)


def test_heif_context_max_decoding_threads():
    ctx = HeifContext()
    # Default is 4 in libheif
    assert ctx.max_decoding_threads == 4
    assert ctx.get_max_decoding_threads() == 4

    # Update to 0 (decode tiles in calling thread)
    ctx.max_decoding_threads = 0
    assert ctx.max_decoding_threads == 0
    assert ctx.get_max_decoding_threads() == 0

    # Update to 8
    ctx.set_max_decoding_threads(8)
    assert ctx.max_decoding_threads == 8

    # Negative values must raise an error
    with pytest.raises((ValueError, TypeError, RuntimeError)):
        ctx.set_max_decoding_threads(-1)


@pytest.mark.asyncio
async def test_async_heif_context_max_decoding_threads():
    async with AsyncHeifContext() as ctx:
        assert ctx.max_decoding_threads == 4
        assert await ctx.get_max_decoding_threads() == 4

        ctx.max_decoding_threads = 0
        assert ctx.max_decoding_threads == 0
        assert await ctx.get_max_decoding_threads() == 0

        await ctx.set_max_decoding_threads(2)
        assert ctx.max_decoding_threads == 2


def test_concurrency_budget_throughput():
    budget = get_concurrency_budget(mode="throughput", total_cpu_quota=8)
    assert isinstance(budget, ConcurrencyBudget)
    assert budget.mode == "throughput"
    assert budget.workers == 8
    assert budget.tile_threads == 0
    assert budget.codec_threads == 1


def test_concurrency_budget_latency():
    budget = get_concurrency_budget(mode="latency", total_cpu_quota=8)
    assert isinstance(budget, ConcurrencyBudget)
    assert budget.mode == "latency"
    assert budget.workers == 1
    assert budget.tile_threads == 4
    assert budget.codec_threads == 4


def test_concurrency_budget_small_quota():
    budget = get_concurrency_budget(mode="latency", total_cpu_quota=2)
    assert budget.workers == 1
    assert budget.tile_threads == 2
    assert budget.codec_threads == 2


def test_encoder_parameter_cache_and_presets():
    enc = HeifEncoder(HeifCompressionFormat.HEVC, preset="ultrafast")
    assert enc.name
    # Fast O(1) parameter presence check
    assert enc.has_parameter("preset")
    assert not enc.has_parameter("non_existent_random_parameter_xyz")

    # Apply all presets cleanly
    for p in ["ultrafast", "fast", "balanced", "quality"]:
        enc.apply_preset(p)
