"""High-precision Depth Map processing, metric distance reconstruction, and visualization.

Compliant with ISO/IEC 23008-12 (HEIF Depth Representation) and Apple AVDepthData.
Provides:
1. DepthMap domain entity with memory-safe reference lifetime guarantees.
2. Metric depth (Z-distance in meters) calculation from disparity/inverse-Z metadata.
3. Zero-dependency microsecond colormap visualization (Turbo, Inferno, Viridis, Grayscale) via Pillow palette.
4. Portrait matte (segmentation alpha mask) extraction.
5. Asynchronous depth map operations (AsyncDepthMap).
"""

from __future__ import annotations

import enum
import functools
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class DepthRepresentationType(enum.IntEnum):
    """HEIF depth representation types according to ISO/IEC 23008-12 & ITU-T H.265 SEI."""

    UNIFORM_INVERSE_Z = 0
    UNIFORM_DISPARITY = 1
    UNIFORM_Z = 2
    NONUNIFORM_DISPARITY = 3


# =========================================================================
# Lightweight Zero-Dependency Colormap Palettes (256x3 RGB bytes)
# =========================================================================


def _eval_poly(c: List[float], x: float) -> float:
    return c[0] + x * (c[1] + x * (c[2] + x * (c[3] + x * (c[4] + x * c[5]))))


def _generate_turbo_palette() -> bytes:
    """Generate Google Turbo colormap 768-byte RGB palette."""
    _tr = [0.13572138, 4.61539260, -42.66032258, 132.13108234, -152.94239396, 59.28637943]
    _tg = [0.09140261, 2.19418839, 4.84296658, -14.18503333, 4.27729857, 2.82956604]
    _tb = [0.10667330, 12.64194608, -60.58204836, 110.36275817, -89.90310912, 27.34824973]
    pal: List[int] = []
    for i in range(256):
        x = i / 255.0
        r = int(max(0, min(255, _eval_poly(_tr, x) * 255.0 + 0.5)))
        g = int(max(0, min(255, _eval_poly(_tg, x) * 255.0 + 0.5)))
        b = int(max(0, min(255, _eval_poly(_tb, x) * 255.0 + 0.5)))
        pal.extend([r, g, b])
    return bytes(pal)


def _generate_inferno_palette() -> bytes:
    """Generate Inferno colormap 768-byte RGB palette."""
    pal: List[int] = []
    for i in range(256):
        x = i / 255.0
        # Smooth interpolation: Black -> Deep Purple -> Orange/Red -> Bright Yellow
        r = int(max(0, min(255, (x**0.7) * 255.0)))
        g = int(max(0, min(255, (max(0.0, x - 0.2) ** 1.5) * 255.0)))
        b = int(max(0, min(255, (np.sin(x * np.pi) * 0.6 if x < 0.6 else max(0.0, 1.0 - (x - 0.6) * 2.5) * 0.6) * 255.0 + (x**3.0) * 180.0)))
        pal.extend([r, g, b])
    return bytes(pal)


def _generate_viridis_palette() -> bytes:
    """Generate Viridis colormap 768-byte RGB palette."""
    pal: List[int] = []
    for i in range(256):
        x = i / 255.0
        r = int(max(0, min(255, (0.28 + 0.72 * (x**2.0)) * 255.0 * (1.0 if x > 0.4 else x * 2.5))))
        g = int(max(0, min(255, (0.05 + 0.95 * (x**0.85)) * 255.0)))
        b = int(max(0, min(255, (0.45 + 0.55 * np.cos(x * np.pi * 0.8)) * 255.0 * (1.0 if x < 0.85 else (1.0 - (x - 0.85) * 4.0)))))
        pal.extend([r, g, b])
    return bytes(pal)


TURBO_PALETTE = _generate_turbo_palette()
INFERNO_PALETTE = _generate_inferno_palette()
VIRIDIS_PALETTE = _generate_viridis_palette()
GRAYSCALE_PALETTE = bytes([i for i in range(256) for _ in range(3)])


# =========================================================================
# Domain Entity: DepthMap
# =========================================================================


class DepthMap:
    """High-Dynamic Range & Metric Depth Map domain entity.

    Encapsulates a HEIF depth image item, its representation info (ISO/IEC 23008-12),
    metric distance calculation, and zero-dependency pseudocolor visualization.

    Maintains a strong reference to the master HeifImageHandle to guarantee
    memory safety and prevent premature garbage collection of native C++ handles.
    """

    def __init__(
        self,
        master_handle: Any,
        aux_handle: Any,
        item_id: int,
    ) -> None:
        self._master_handle = master_handle
        self._aux_handle = aux_handle
        self._item_id = item_id

    @property
    def master_handle(self) -> Any:
        """The master/primary image handle."""
        return self._master_handle

    @property
    def aux_handle(self) -> Any:
        """The auxiliary image handle containing the depth map pixel data."""
        return self._aux_handle

    @property
    def item_id(self) -> int:
        """The auxiliary depth item ID."""
        return self._item_id

    @property
    def width(self) -> int:
        """Width of the depth map image."""
        return self._aux_handle.width

    @property
    def height(self) -> int:
        """Height of the depth map image."""
        return self._aux_handle.height

    @property
    def bit_depth(self) -> int:
        """Bit depth per depth pixel (typically 8-bit or 16-bit LiDAR)."""
        return getattr(self._aux_handle, "luma_bits_per_pixel", 8)

    @functools.cached_property
    def info(self) -> Optional[Any]:
        """Depth representation metadata (HeifDepthRepresentationInfo) if present."""
        try:
            return self._master_handle.get_depth_representation_info(self._item_id)
        except Exception:
            return None

    @property
    def depth_type(self) -> int:
        """HEIF depth representation type (0=Inverse Z, 1=Disparity, 2=Z, 3=Non-uniform)."""
        if self.info is not None:
            return getattr(self.info, "depth_representation_type", 0)
        return 0

    @property
    def is_disparity(self) -> bool:
        """True if pixel values represent disparity / inverse-Z (higher values = closer objects)."""
        return self.depth_type in (
            DepthRepresentationType.UNIFORM_INVERSE_Z,
            DepthRepresentationType.UNIFORM_DISPARITY,
            DepthRepresentationType.NONUNIFORM_DISPARITY,
        )

    @property
    def z_near(self) -> Optional[float]:
        """Nearest depth plane distance in meters (if calibrated)."""
        if self.info is not None and getattr(self.info, "has_z_near", False):
            return float(self.info.z_near)
        return None

    @property
    def z_far(self) -> Optional[float]:
        """Farthest depth plane distance in meters (if calibrated)."""
        if self.info is not None and getattr(self.info, "has_z_far", False):
            return float(self.info.z_far)
        return None

    @property
    def d_min(self) -> Optional[float]:
        """Minimum disparity value (if calibrated)."""
        if self.info is not None and getattr(self.info, "has_d_min", False):
            return float(self.info.d_min)
        return None

    @property
    def d_max(self) -> Optional[float]:
        """Maximum disparity value (if calibrated)."""
        if self.info is not None and getattr(self.info, "has_d_max", False):
            return float(self.info.d_max)
        return None

    @property
    def has_metric_info(self) -> bool:
        """True if depth map contains calibrated z_near and z_far metric parameters."""
        return (
            self.z_near is not None
            and self.z_far is not None
            and self.z_far > self.z_near > 0.0
        )

    def decode(
        self,
        normalize: bool = False,
        invert_if_disparity: bool = False,
    ) -> np.ndarray:
        """Decode primary depth image and return as a 2D numpy array.

        Args:
            normalize: If True, scale pixel values to float32 range [0.0, 1.0].
            invert_if_disparity: If True and data is disparity, invert values so
                                0.0 represents closest objects and 1.0 represents infinity.
        """
        from ._pylibheif import HeifChannel, HeifChroma, HeifColorspace

        decoded = self._aux_handle.decode(HeifColorspace.Monochrome, HeifChroma.Monochrome)
        plane = decoded.get_plane(HeifChannel.Y)
        raw_arr = np.asarray(plane)

        if not normalize:
            return raw_arr

        # Normalize to float32 [0.0, 1.0]
        max_val = float((1 << self.bit_depth) - 1) if self.bit_depth > 0 else 255.0
        norm_arr = raw_arr.astype(np.float32) / max_val
        np.clip(norm_arr, 0.0, 1.0, out=norm_arr)

        if invert_if_disparity and self.is_disparity:
            norm_arr = 1.0 - norm_arr

        return norm_arr

    def decode_image(self) -> Any:
        """Decode depth image and return as a native HeifImage instance."""
        from ._pylibheif import HeifChroma, HeifColorspace

        return self._aux_handle.decode(
            HeifColorspace.Monochrome, HeifChroma.Monochrome
        )

    def to_metric_depth(self) -> Optional[np.ndarray]:
        """Compute true physical metric distance matrix Z (in meters) as float32.

        Uses the exact ISO/IEC 23008-12 and ITU-T H.265 Depth Representation formulas.
        Returns None if calibrated metric depth parameters (z_near / z_far) are absent.
        """
        if not self.has_metric_info or self.z_near is None or self.z_far is None:
            return None

        # Normalized values in [0.0, 1.0]
        y = self.decode(normalize=True)
        z_near = float(self.z_near)
        z_far = float(self.z_far)

        if self.depth_type == DepthRepresentationType.UNIFORM_INVERSE_Z:
            # 1 / Z = (1 / z_far) + y * (1 / z_near - 1 / z_far)
            inv_z_far = 1.0 / z_far
            inv_z_near = 1.0 / z_near
            inv_z = inv_z_far + y * (inv_z_near - inv_z_far)
            # Avoid division by zero
            np.maximum(inv_z, 1e-7, out=inv_z)
            z_metric = 1.0 / inv_z
            return z_metric.astype(np.float32)

        elif self.depth_type == DepthRepresentationType.UNIFORM_Z:
            # Z = z_near + y * (z_far - z_near)
            z_metric = z_near + y * (z_far - z_near)
            return z_metric.astype(np.float32)

        elif self.depth_type == DepthRepresentationType.UNIFORM_DISPARITY and self.d_min is not None and self.d_max is not None:
            disp = self.d_min + y * (self.d_max - self.d_min)
            np.maximum(disp, 1e-7, out=disp)
            z_metric = 1.0 / disp
            return z_metric.astype(np.float32)

        return None

    def to_pillow(
        self,
        colormap: Optional[str] = "turbo",
        size: Optional[Tuple[int, int]] = None,
        resample: Any = None,
    ) -> Any:
        """Render depth map as a Pillow Image with zero external dependencies.

        Args:
            colormap: 'turbo' (default, high contrast), 'inferno', 'viridis', or 'grayscale'/'none'.
            size: Optional (width, height) to resize the output depth image to match master image dimensions.
            resample: Optional PIL resampling filter (defaults to BILINEAR if size is specified).
        """
        try:
            from PIL import Image
        except ImportError as e:
            raise ImportError(
                "DepthMap.to_pillow() requires Pillow. Install via `pip install 'pylibheif[pillow]'`"
            ) from e

        norm = self.decode(normalize=True)
        u8 = (norm * 255.0 + 0.5).astype(np.uint8)
        img = Image.fromarray(u8, mode="L")

        cmap_lower = (colormap or "grayscale").lower()
        if cmap_lower in ("turbo", "google_turbo"):
            p_img = img.convert("P")
            p_img.putpalette(TURBO_PALETTE)
            res = p_img.convert("RGB")
        elif cmap_lower == "inferno":
            p_img = img.convert("P")
            p_img.putpalette(INFERNO_PALETTE)
            res = p_img.convert("RGB")
        elif cmap_lower == "viridis":
            p_img = img.convert("P")
            p_img.putpalette(VIRIDIS_PALETTE)
            res = p_img.convert("RGB")
        else:
            res = img

        if size is not None and (res.width, res.height) != size:
            resample_filter = resample if resample is not None else Image.Resampling.BILINEAR
            res = res.resize(size, resample=resample_filter)

        return res

    def to_dict(self) -> Dict[str, Any]:
        """Serialize depth map metadata to dictionary."""
        return {
            "width": self.width,
            "height": self.height,
            "bit_depth": self.bit_depth,
            "depth_type": self.depth_type,
            "is_disparity": self.is_disparity,
            "has_metric_info": self.has_metric_info,
            "z_near": self.z_near,
            "z_far": self.z_far,
            "d_min": self.d_min,
            "d_max": self.d_max,
        }

    def __repr__(self) -> str:
        metric_str = f"range=[{self.z_near:.2f}m, {self.z_far:.2f}m]" if self.has_metric_info else "relative"
        return (
            f"<pylibheif.DepthMap size={self.width}x{self.height} "
            f"bit_depth={self.bit_depth} type={self.depth_type} ({metric_str})>"
        )


def extract_depth_map(handle: Any) -> Optional[DepthMap]:
    """Inspect a HeifImageHandle and return a DepthMap domain entity if present, or None."""
    if handle is None:
        return None
    try:
        # 1. Standard HEIF depth track query
        if getattr(handle, "has_depth_image", False):
            ids = handle.get_depth_image_ids()
            if ids:
                item_id = ids[0]
                aux_handle = handle.get_depth_image_handle(item_id)
                return DepthMap(master_handle=handle, aux_handle=aux_handle, item_id=item_id)

        # 2. Auxiliary track query for standard MPEG depth or Apple depth URNs
        if hasattr(handle, "get_auxiliary_image_ids"):
            for aid in handle.get_auxiliary_image_ids():
                aux_h = handle.get_auxiliary_image_handle(aid)
                atype = aux_h.get_auxiliary_type().lower()
                if (
                    "depth" in atype
                    or "auxid:1" in atype
                    or "disparity" in atype
                ):
                    return DepthMap(master_handle=handle, aux_handle=aux_h, item_id=aid)
        return None
    except Exception:
        return None


def extract_portrait_matte(handle: Any) -> Optional[np.ndarray]:
    """Extract Apple Portrait Matte (hair/subject foreground alpha mask) if present."""
    if handle is None:
        return None
    try:
        for aid in handle.get_auxiliary_image_ids():
            aux_handle = handle.get_auxiliary_image_handle(aid)
            atype = aux_handle.get_auxiliary_type().lower()
            if "portraitmatte" in atype or "matte" in atype:
                from ._pylibheif import HeifChannel, HeifChroma, HeifColorspace

                decoded = aux_handle.decode(HeifColorspace.Monochrome, HeifChroma.Monochrome)
                plane = decoded.get_plane(HeifChannel.Y)
                return np.asarray(plane)
    except Exception:
        pass
    return None


# =========================================================================
# Domain Entity: AsyncDepthMap
# =========================================================================


class AsyncDepthMap:
    """Asynchronous Depth Map domain entity attached to AsyncHeifImageHandle."""

    def __init__(
        self,
        master_handle: Any,
        sync_depth_map: DepthMap,
        executor: Any = None,
    ) -> None:
        self._master_handle = master_handle
        self._sync_depth_map = sync_depth_map
        self._executor = executor

    @property
    def master_handle(self) -> Any:
        return self._master_handle

    @property
    def aux_handle(self) -> Any:
        from ._async import AsyncHeifImageHandle

        return AsyncHeifImageHandle(
            self._sync_depth_map.aux_handle, executor=self._executor
        )

    @property
    def item_id(self) -> int:
        return self._sync_depth_map.item_id

    @property
    def width(self) -> int:
        return self._sync_depth_map.width

    @property
    def height(self) -> int:
        return self._sync_depth_map.height

    @property
    def bit_depth(self) -> int:
        return self._sync_depth_map.bit_depth

    @property
    def info(self) -> Optional[Any]:
        return self._sync_depth_map.info

    @property
    def depth_type(self) -> int:
        return self._sync_depth_map.depth_type

    @property
    def is_disparity(self) -> bool:
        return self._sync_depth_map.is_disparity

    @property
    def z_near(self) -> Optional[float]:
        return self._sync_depth_map.z_near

    @property
    def z_far(self) -> Optional[float]:
        return self._sync_depth_map.z_far

    @property
    def has_metric_info(self) -> bool:
        return self._sync_depth_map.has_metric_info

    def decode(
        self,
        normalize: bool = False,
        invert_if_disparity: bool = False,
    ) -> np.ndarray:
        return self._sync_depth_map.decode(
            normalize=normalize, invert_if_disparity=invert_if_disparity
        )

    async def decode_async(
        self,
        normalize: bool = False,
        invert_if_disparity: bool = False,
    ) -> np.ndarray:
        from ._concurrency import _run_in_executor

        return await _run_in_executor(
            self._executor,
            self._sync_depth_map.decode,
            normalize,
            invert_if_disparity,
        )

    def decode_image(self) -> Any:
        return self._sync_depth_map.decode_image()

    async def decode_image_async(self) -> Any:
        from ._concurrency import _run_in_executor

        return await _run_in_executor(
            self._executor, self._sync_depth_map.decode_image
        )

    def to_metric_depth(self) -> Optional[np.ndarray]:
        return self._sync_depth_map.to_metric_depth()

    async def to_metric_depth_async(self) -> Optional[np.ndarray]:
        from ._concurrency import _run_in_executor

        return await _run_in_executor(
            self._executor, self._sync_depth_map.to_metric_depth
        )

    def to_pillow(
        self,
        colormap: Optional[str] = "turbo",
        size: Optional[Tuple[int, int]] = None,
        resample: Any = None,
    ) -> Any:
        return self._sync_depth_map.to_pillow(
            colormap=colormap, size=size, resample=resample
        )

    async def to_pillow_async(
        self,
        colormap: Optional[str] = "turbo",
        size: Optional[Tuple[int, int]] = None,
        resample: Any = None,
    ) -> Any:
        from ._concurrency import _run_in_executor

        return await _run_in_executor(
            self._executor,
            self._sync_depth_map.to_pillow,
            colormap,
            size,
            resample,
        )

    def to_dict(self) -> Dict[str, Any]:
        return self._sync_depth_map.to_dict()

    def __repr__(self) -> str:
        return (
            f"<pylibheif.AsyncDepthMap size={self.width}x{self.height} "
            f"bit_depth={self.bit_depth}>"
        )


def extract_async_depth_map(async_handle: Any) -> Optional[AsyncDepthMap]:
    """Extract an AsyncDepthMap from an AsyncHeifImageHandle if present."""
    if async_handle is None:
        return None
    sync_handle = getattr(async_handle, "_handle", async_handle)
    sync_dm = extract_depth_map(sync_handle)
    if sync_dm is None:
        return None
    executor = getattr(async_handle, "_executor", None)
    return AsyncDepthMap(
        master_handle=async_handle,
        sync_depth_map=sync_dm,
        executor=executor,
    )
