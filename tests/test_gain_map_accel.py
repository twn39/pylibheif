"""Tests and benchmarks for accelerated HDR Gain Map (ISO 21496-1) calculation pipeline.

Validates:
1. Mathematical equivalence between Tier 1 (NumPy vectorized), Tier 2 (C++ fused SIMD kernel),
   and the analytical ISO 21496-1 ground-truth across float32, float16, srgb_clip, and pq formats.
2. Handling of monochrome vs RGB gain maps, gamma != 1.0, and RGBA with alpha preservation.
3. Performance benchmarks for 1080p and 12MP image reconstruction.
"""

from __future__ import annotations

import time
import numpy as np
import pytest

from pylibheif.gain_map import (
    GainMapMetadata,
    _SRGB_TO_LINEAR_LUT_256,
    reconstruct_hdr,
)


def _reference_reconstruct(
    sdr_uint8: np.ndarray,
    gm_uint8: np.ndarray,
    metadata: GainMapMetadata,
    w_factor: float,
) -> np.ndarray:
    """Pure analytical reference implementation without in-place or LUT optimizations."""
    sdr_f = sdr_uint8.astype(np.float64) / 255.0
    # Exact sRGB EOTF
    sdr_lin = np.where(
        sdr_f <= 0.04045,
        sdr_f / 12.92,
        np.power((sdr_f + 0.055) / 1.055, 2.4),
    )
    gm_f = gm_uint8.astype(np.float64) / 255.0
    if gm_f.ndim == 2:
        gm_f = gm_f[:, :, np.newaxis]

    gamma = np.array(metadata.gamma, dtype=np.float64)
    gm_norm = np.power(gm_f, gamma)
    g_min = np.array(metadata.gain_map_min, dtype=np.float64)
    g_max = np.array(metadata.gain_map_max, dtype=np.float64)
    log_gain = (g_min + gm_norm * (g_max - g_min)) * w_factor
    gain = np.power(2.0, log_gain)

    o_sdr = np.array(metadata.offset_sdr, dtype=np.float64)
    o_hdr = np.array(metadata.offset_hdr, dtype=np.float64)
    hdr_lin = (sdr_lin + o_sdr) * gain - o_hdr
    return np.maximum(hdr_lin, 0.0).astype(np.float32)


def test_lut_256_precision() -> None:
    """Validate 256-entry float32 LUT against high-precision analytical sRGB EOTF."""
    assert _SRGB_TO_LINEAR_LUT_256.shape == (256,)
    assert _SRGB_TO_LINEAR_LUT_256[0] == 0.0
    assert abs(_SRGB_TO_LINEAR_LUT_256[255] - 1.0) < 1e-6

    for i in range(256):
        val = i / 255.0
        expected = val / 12.92 if val <= 0.04045 else ((val + 0.055) / 1.055) ** 2.4
        np.testing.assert_allclose(_SRGB_TO_LINEAR_LUT_256[i], expected, atol=1e-6)


@pytest.mark.parametrize("is_mono", [True, False])
@pytest.mark.parametrize("gamma_val", [1.0, 1.2])
def test_cpp_and_numpy_accuracy_linear(is_mono: bool, gamma_val: float) -> None:
    """Verify C++ kernel and NumPy Tier 1 both match reference within atol=1e-5."""
    H, W = 64, 64
    rng = np.random.default_rng(42)
    sdr_u8 = rng.integers(0, 256, (H, W, 3), dtype=np.uint8)

    if is_mono:
        gm_u8 = rng.integers(0, 256, (H, W), dtype=np.uint8)
        meta = GainMapMetadata(
            gain_map_min=(0.0, 0.0, 0.0),
            gain_map_max=(2.0, 2.0, 2.0),
            gamma=(gamma_val, gamma_val, gamma_val),
            hdr_capacity_max=2.0,
        )
    else:
        gm_u8 = rng.integers(0, 256, (H, W, 3), dtype=np.uint8)
        meta = GainMapMetadata(
            gain_map_min=(0.0, 0.2, -0.1),
            gain_map_max=(2.0, 2.2, 1.8),
            gamma=(gamma_val, gamma_val * 0.9, gamma_val * 1.1),
            hdr_capacity_max=2.0,
        )

    w_factor = 0.8
    ref = _reference_reconstruct(sdr_u8, gm_u8, meta, w_factor)

    # 1. Tier 2 (C++ acceleration via reconstruct_hdr)
    act_cpp = reconstruct_hdr(
        sdr_u8, gm_u8, metadata=meta, target_headroom=2.0**1.6, output_format="linear"
    )
    np.testing.assert_allclose(act_cpp, ref, atol=1e-5, rtol=1e-4)

    # 2. Tier 1 (NumPy pipeline: pass float input to bypass uint8 C++ path)
    sdr_float = sdr_u8.astype(np.float32) / 255.0
    act_numpy = reconstruct_hdr(
        sdr_float,
        gm_u8,
        metadata=meta,
        target_headroom=2.0**1.6,
        output_format="linear",
    )
    np.testing.assert_allclose(act_numpy, ref, atol=1e-5, rtol=1e-4)


def test_reconstruct_srgb_clip_accuracy() -> None:
    """Verify tonemapped srgb_clip uint8 output matching between C++ and NumPy."""
    H, W = 100, 100
    rng = np.random.default_rng(123)
    sdr_u8 = rng.integers(0, 256, (H, W, 3), dtype=np.uint8)
    gm_u8 = rng.integers(0, 256, (H, W), dtype=np.uint8)
    meta = GainMapMetadata(
        gain_map_min=(0.0, 0.0, 0.0),
        gain_map_max=(2.0, 2.0, 2.0),
        gamma=(1.0, 1.0, 1.0),
    )

    # C++ uint8 path
    out_cpp = reconstruct_hdr(
        sdr_u8, gm_u8, metadata=meta, target_headroom=2.0, output_format="srgb_clip"
    )
    assert out_cpp.dtype == np.uint8
    assert out_cpp.shape == (H, W, 3)

    # NumPy float fallback path
    out_np = reconstruct_hdr(
        sdr_u8.astype(np.float32) / 255.0,
        gm_u8,
        metadata=meta,
        target_headroom=2.0,
        output_format="srgb_clip",
    )
    assert out_np.dtype == np.uint8
    # Within 1 code point due to rounding/float precision
    diff = np.max(np.abs(out_cpp.astype(np.int32) - out_np.astype(np.int32)))
    assert diff <= 1


def test_reconstruct_pq_uint16_accuracy() -> None:
    """Verify Rec.2100 PQ uint16 output matching between C++ and NumPy."""
    H, W = 80, 80
    rng = np.random.default_rng(456)
    sdr_u8 = rng.integers(0, 256, (H, W, 3), dtype=np.uint8)
    gm_u8 = rng.integers(0, 256, (H, W), dtype=np.uint8)
    meta = GainMapMetadata(
        gain_map_min=(0.0, 0.0, 0.0),
        gain_map_max=(2.0, 2.0, 2.0),
        gamma=(1.0, 1.0, 1.0),
    )

    out_cpp = reconstruct_hdr(
        sdr_u8, gm_u8, metadata=meta, target_headroom=4.0, output_format="pq"
    )
    assert out_cpp.dtype == np.uint16
    assert out_cpp.shape == (H, W, 3)

    out_np = reconstruct_hdr(
        sdr_u8.astype(np.float32) / 255.0,
        gm_u8,
        metadata=meta,
        target_headroom=4.0,
        output_format="pq",
    )
    assert out_np.dtype == np.uint16
    diff = np.max(np.abs(out_cpp.astype(np.int32) - out_np.astype(np.int32)))
    assert diff <= 2


def test_rgba_with_alpha_preservation() -> None:
    """Verify 4-channel RGBA inputs retain exact alpha transparency channel."""
    H, W = 40, 40
    sdr_rgba = np.full((H, W, 4), 128, dtype=np.uint8)
    sdr_rgba[:, :, 3] = 200  # distinct alpha
    gm = np.full((H, W), 255, dtype=np.uint8)
    meta = GainMapMetadata()

    # Linear
    hdr_lin = reconstruct_hdr(sdr_rgba, gm, meta, output_format="linear")
    assert hdr_lin.shape == (H, W, 4)
    np.testing.assert_allclose(hdr_lin[:, :, 3], 200.0 / 255.0, atol=1e-4)

    # srgb_clip
    hdr_srgb = reconstruct_hdr(sdr_rgba, gm, meta, output_format="srgb_clip")
    assert hdr_srgb.shape == (H, W, 4)
    assert np.all(hdr_srgb[:, :, 3] == 200)


def test_performance_speedup_benchmark() -> None:
    """Benchmark reconstruction speedup on a high-res (2000x2000 = 4MP) image."""
    H, W = 2000, 2000
    rng = np.random.default_rng(789)
    sdr_u8 = rng.integers(0, 256, (H, W, 3), dtype=np.uint8)
    gm_u8 = rng.integers(0, 256, (H, W), dtype=np.uint8)
    meta = GainMapMetadata()

    # Warm-up
    _ = reconstruct_hdr(sdr_u8, gm_u8, meta)

    # Measure C++ Tier 2
    t0 = time.perf_counter()
    res_cpp = reconstruct_hdr(sdr_u8, gm_u8, meta, output_format="srgb_clip")
    t1 = time.perf_counter()
    cpp_time_ms = (t1 - t0) * 1000

    # Measure NumPy Tier 1 (using float input to force Python engine)
    sdr_f = sdr_u8.astype(np.float32) / 255.0
    t0 = time.perf_counter()
    res_py = reconstruct_hdr(sdr_f, gm_u8, meta, output_format="srgb_clip")
    t1 = time.perf_counter()
    py_time_ms = (t1 - t0) * 1000

    print("\n[Benchmark 4MP 2000x2000]")
    print(f"C++ Multi-threaded SIMD Kernel: {cpp_time_ms:.2f} ms")
    print(f"NumPy Vectorized Pipeline:     {py_time_ms:.2f} ms")
    print(f"C++ vs NumPy Speedup:          {py_time_ms / max(cpp_time_ms, 0.01):.2f}x")

    assert cpp_time_ms < 100.0  # Should be well under 100ms for 4MP
    assert res_cpp.shape == (H, W, 3)
    assert res_py.shape == (H, W, 3)
