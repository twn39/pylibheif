"""Thread pooling, cgroups-aware CPU allocation, and concurrency budgeting."""

from __future__ import annotations
import atexit
import asyncio
import concurrent.futures
import dataclasses
import math
import os
import threading
from typing import Optional, Literal


def _detect_usable_cpu_count() -> int:
    """Detect the number of usable CPU cores, taking into account cgroups quotas and affinities."""
    if hasattr(os, "process_cpu_count"):
        try:
            cnt = os.process_cpu_count()
            if cnt is not None and cnt > 0:
                return cnt
        except Exception:
            pass

    # Check Linux cgroups v2 quota (/sys/fs/cgroup/cpu.max)
    try:
        with open("/sys/fs/cgroup/cpu.max", "r", encoding="utf-8") as f:
            quota_s, period_s = f.read().strip().split()
            if quota_s != "max":
                quota = int(quota_s)
                period = int(period_s)
                if quota > 0 and period > 0:
                    return max(1, math.ceil(quota / period))
    except (OSError, ValueError):
        pass

    # Check Linux cgroups v1 quota (/sys/fs/cgroup/cpu/cpu.cfs_quota_us)
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "r", encoding="utf-8") as fq:
            quota = int(fq.read().strip())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "r", encoding="utf-8") as fp:
            period = int(fp.read().strip())
        if quota > 0 and period > 0:
            return max(1, math.ceil(quota / period))
    except (OSError, ValueError):
        pass

    return max(1, os.cpu_count() or 1)


@dataclasses.dataclass(frozen=True)
class ConcurrencyBudget:
    """Thread and worker resource budget for balanced HEIF/AVIF processing."""

    mode: str
    workers: int
    tile_threads: int
    codec_threads: int


def get_concurrency_budget(
    mode: Literal["throughput", "latency"] = "throughput",
    total_cpu_quota: Optional[int] = None,
) -> ConcurrencyBudget:
    """Compute optimal concurrency budget avoiding thread oversubscription.

    Modes:
    - 'throughput' (Default for batch/multi-image):
      Maximizes overall image throughput by scaling worker threads across cores,
      while locking intra-image tile and codec threads to 0/1. Avoids inter-core
      spinlocks, L1/L2 cache evictions, and Amdahl's law bottleneck on single frames.
    - 'latency' (Optimized for interactive single-image decoding/encoding):
      Allocates all hardware capability to a single worker, activating both tile-level
      parallelism and up to 4 intra-frame codec threads.
    """
    usable = (
        total_cpu_quota
        if (total_cpu_quota is not None and total_cpu_quota > 0)
        else _detect_usable_cpu_count()
    )
    if mode == "latency":
        tile_threads = min(4, usable)
        codec_threads = min(4, usable)
        return ConcurrencyBudget(
            mode="latency",
            workers=1,
            tile_threads=tile_threads,
            codec_threads=codec_threads,
        )

    # Throughput mode: one task per CPU core, single-threaded per image
    return ConcurrencyBudget(
        mode="throughput",
        workers=max(1, usable),
        tile_threads=0,  # Decode tiles sequentially in the worker thread
        codec_threads=1,  # Single thread per codec instance
    )


_default_codec_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
_default_codec_executor_lock = threading.Lock()


def get_default_codec_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Get or lazily initialize the dedicated thread pool executor for CPU-bound codec operations."""
    global _default_codec_executor
    if _default_codec_executor is None:
        with _default_codec_executor_lock:
            if _default_codec_executor is None:
                usable = _detect_usable_cpu_count()
                workers = max(1, usable // 2)
                _default_codec_executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=workers,
                    thread_name_prefix="pylibheif-codec",
                )
    return _default_codec_executor


def set_default_codec_executor(
    executor: Optional[concurrent.futures.ThreadPoolExecutor],
) -> None:
    """Set or replace the default codec executor.

    If an existing internal executor was active, it is cleanly shut down.
    """
    global _default_codec_executor
    with _default_codec_executor_lock:
        old_executor = _default_codec_executor
        _default_codec_executor = executor
    if old_executor is not None and old_executor is not executor:
        try:
            old_executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            old_executor.shutdown(wait=False)


def shutdown_default_codec_executor(
    wait: bool = False, cancel_futures: bool = True
) -> None:
    """Explicitly shut down the dedicated codec thread pool executor."""
    global _default_codec_executor
    with _default_codec_executor_lock:
        executor = _default_codec_executor
        _default_codec_executor = None
    if executor is not None:
        try:
            executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        except TypeError:
            executor.shutdown(wait=wait)


atexit.register(shutdown_default_codec_executor, wait=False, cancel_futures=True)


async def _run_in_executor(
    executor: Optional[concurrent.futures.Executor], func, *args
):
    """Run CPU-bound callable in the designated thread pool executor without blocking the asyncio loop."""
    exec_to_use = executor if executor is not None else get_default_codec_executor()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(exec_to_use, func, *args)
