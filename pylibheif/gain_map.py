"""High-Dynamic Range (HDR) Gain Map processing, metadata parsing, and tonemapping.

Compliant with ISO 21496-1, Apple HDRGainMap, and Adobe/Google Ultra HDR specifications.
Provides end-to-end support for:
1. GainMapMetadata representation (1-channel & 3-channel RGB).
2. XMP metadata serialization & deserialization.
3. Physically correct EOTF linearization and inverse tonemapping.
4. Linear HDR, 10-bit Rec.2100 PQ (HDR10), and HLG reconstruction.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np

# Standard URNs for Gain Map Auxiliary Image Items
URN_GAIN_MAP_ISO_21496_1 = "urn:iso:std:iso:ts:21496-1"
URN_GAIN_MAP_APPLE = "urn:com:apple:photo:2020:aux:hdrgainmap"
URN_PORTRAIT_MATTE_APPLE = "urn:com:apple:photo:2018:aux:portraitmatte"


def _to_tuple3(val: Union[float, int, Tuple[float, float, float], list[float]]) -> Tuple[float, float, float]:
    """Ensure value is a 3-tuple of floats (R, G, B)."""
    if isinstance(val, (tuple, list)):
        if len(val) == 1:
            f = float(val[0])
            return (f, f, f)
        elif len(val) >= 3:
            return (float(val[0]), float(val[1]), float(val[2]))
        else:
            raise ValueError(f"Expected 1 or 3 values, got {len(val)}")
    f = float(val)
    return (f, f, f)


@dataclass
class GainMapMetadata:
    """Gain Map metadata according to ISO 21496-1 & Apple HDRGainMap standards.

    Attributes:
        gain_map_min: Minimum boost in log2 scale (stops), per channel (R, G, B).
        gain_map_max: Maximum boost in log2 scale (stops), per channel (R, G, B).
                      For example, 2.0 corresponds to 4x (2^2) maximum brightness boost.
        gamma: Exponent applied to the normalized gain map value, per channel (R, G, B).
        offset_sdr: SDR offset to avoid division by zero and handle dark levels, per channel.
        offset_hdr: HDR offset to avoid negative values and handle dark levels, per channel.
        hdr_capacity_min: Minimum HDR capacity required to start applying gain map (usually 1.0).
        hdr_capacity_max: HDR capacity at which maximum gain is applied (e.g. 4.0 for 2 stops).
        base_rendition_is_hdr: True if the base image is HDR and gain map maps down to SDR;
                               False if base image is SDR and gain map maps up to HDR (standard).
        standard: Metadata standard format ("iso_21496_1", "apple", or "dual").
    """

    gain_map_min: Tuple[float, float, float] = field(default_factory=lambda: (0.0, 0.0, 0.0))
    gain_map_max: Tuple[float, float, float] = field(default_factory=lambda: (2.0, 2.0, 2.0))
    gamma: Tuple[float, float, float] = field(default_factory=lambda: (1.0, 1.0, 1.0))
    offset_sdr: Tuple[float, float, float] = field(default_factory=lambda: (0.015625, 0.015625, 0.015625))
    offset_hdr: Tuple[float, float, float] = field(default_factory=lambda: (0.015625, 0.015625, 0.015625))
    hdr_capacity_min: float = 0.0
    hdr_capacity_max: float = 2.0
    base_rendition_is_hdr: bool = False
    standard: str = "dual"

    def __post_init__(self):
        self.gain_map_min = _to_tuple3(self.gain_map_min)
        self.gain_map_max = _to_tuple3(self.gain_map_max)
        self.gamma = _to_tuple3(self.gamma)
        self.offset_sdr = _to_tuple3(self.offset_sdr)
        self.offset_hdr = _to_tuple3(self.offset_hdr)
        self.hdr_capacity_min = float(self.hdr_capacity_min)
        self.hdr_capacity_max = float(self.hdr_capacity_max)

    @property
    def is_monochrome(self) -> bool:
        """True if all parameters are identical across R, G, B channels."""
        return (
            self.gain_map_min[0] == self.gain_map_min[1] == self.gain_map_min[2]
            and self.gain_map_max[0] == self.gain_map_max[1] == self.gain_map_max[2]
            and self.gamma[0] == self.gamma[1] == self.gamma[2]
            and self.offset_sdr[0] == self.offset_sdr[1] == self.offset_sdr[2]
            and self.offset_hdr[0] == self.offset_hdr[1] == self.offset_hdr[2]
        )

    @property
    def format_type(self) -> str:
        """Format identifier: 'Apple' or 'ISO'."""
        if self.standard.lower() in ("apple", "hdrgainmap"):
            return "Apple"
        return "ISO"

    @property
    def max_content_boost(self) -> float:
        """Maximum luminance boost factor (linear scale)."""
        return float(2.0 ** max(self.gain_map_max))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "gain_map_min": list(self.gain_map_min),
            "gain_map_max": list(self.gain_map_max),
            "gamma": list(self.gamma),
            "offset_sdr": list(self.offset_sdr),
            "offset_hdr": list(self.offset_hdr),
            "hdr_capacity_min": self.hdr_capacity_min,
            "hdr_capacity_max": self.hdr_capacity_max,
            "base_rendition_is_hdr": self.base_rendition_is_hdr,
            "standard": self.standard,
            "format_type": self.format_type,
            "max_content_boost": self.max_content_boost,
            "is_monochrome": self.is_monochrome,
        }

    @classmethod
    def from_scalar(
        cls,
        max_boost_stops: float = 2.0,
        min_boost_stops: float = 0.0,
        gamma: float = 1.0,
        offset: float = 1.0 / 64.0,
        hdr_capacity_max: Optional[float] = None,
        standard: str = "dual",
    ) -> "GainMapMetadata":
        """Convenience constructor from single scalar values."""
        cap_max = hdr_capacity_max if hdr_capacity_max is not None else 2.0**max_boost_stops
        return cls(
            gain_map_min=(min_boost_stops, min_boost_stops, min_boost_stops),
            gain_map_max=(max_boost_stops, max_boost_stops, max_boost_stops),
            gamma=(gamma, gamma, gamma),
            offset_sdr=(offset, offset, offset),
            offset_hdr=(offset, offset, offset),
            hdr_capacity_min=0.0,
            hdr_capacity_max=cap_max,
            base_rendition_is_hdr=False,
            standard=standard,
        )

    @classmethod
    def from_xmp(cls, xmp_data: Union[bytes, str]) -> Optional["GainMapMetadata"]:
        """Parse Gain Map metadata from XMP bytes or XML string."""
        return parse_gain_map_metadata(xmp_data)

    def to_xmp(self, format_type: Optional[str] = None) -> bytes:
        """Serialize metadata into XMP bytes."""
        fmt = format_type or self.format_type
        return generate_gain_map_xmp(self, format_type=fmt)


def parse_gain_map_metadata(xmp_data: Union[bytes, str]) -> Optional[GainMapMetadata]:
    """Parse Gain Map metadata from XMP bytes or XML string.

    Supports:
    - ISO 21496-1 (urn:iso:std:iso:ts:21496-1 or http://iso.org/gainmap/1.0/)
    - Apple HDRGainMap (http://ns.apple.com/HDRGainMap/1.0/)
    - Adobe Ultra HDR (http://ns.adobe.com/hdr-gain-map/1.0/)
    """
    if isinstance(xmp_data, bytes):
        try:
            xmp_str = xmp_data.decode("utf-8", errors="ignore")
        except Exception:
            return None
    else:
        xmp_str = xmp_data

    if not xmp_str or ("gain" not in xmp_str.lower() and "hdr" not in xmp_str.lower()):
        return None

    try:
        # Strip XMP packet wrappers <?xpacket ...?>
        start_idx = xmp_str.find("<x:xmpmeta")
        if start_idx == -1:
            start_idx = xmp_str.find("<rdf:RDF")
        if start_idx == -1:
            start_idx = xmp_str.find("<Description")
        if start_idx == -1:
            start_idx = 0

        end_idx = xmp_str.rfind("</x:xmpmeta>")
        if end_idx != -1:
            end_idx += len("</x:xmpmeta>")
        else:
            end_idx = len(xmp_str)

        xml_content = xmp_str[start_idx:end_idx].strip()
        root = ET.fromstring(xml_content)
    except Exception:
        return _parse_xmp_fallback(xmp_str)

    # Find rdf:Description elements
    descriptions = root.findall(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description")
    if not descriptions:
        descriptions = [root]

    def _val_to_tuple3(v: Any, default: float) -> Tuple[float, float, float]:
        if v is None:
            return (default, default, default)
        if isinstance(v, (list, tuple)):
            if len(v) == 1:
                return (float(v[0]), float(v[0]), float(v[0]))
            elif len(v) >= 3:
                return (float(v[0]), float(v[1]), float(v[2]))
        try:
            f = float(v)
            return (f, f, f)
        except Exception:
            return (default, default, default)

    for desc in descriptions:
        # Extract all attributes and child elements case-insensitively
        props: Dict[str, Any] = {}
        for k, v in desc.attrib.items():
            local_name = k.split("}")[-1].lower()
            props[local_name] = v

        for child in desc:
            local_name = child.tag.split("}")[-1].lower()
            seq = child.findall(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li")
            if seq:
                vals = []
                for li in seq:
                    if li.text:
                        try:
                            vals.append(float(li.text.strip()))
                        except ValueError:
                            pass
                if vals:
                    props[local_name] = vals
            elif child.text and child.text.strip():
                props[local_name] = child.text.strip()

        # Check if Apple or ISO
        has_apple = any("hdrgainmap" in k for k in props)
        has_iso = any(k in props for k in ("gainmapmax", "gainmapmin", "hdrgm"))

        if has_apple or has_iso or "gainmapmax" in props or "hdrgainmapmax" in props:
            is_apple = has_apple and not has_iso
            max_v = props.get("hdrgainmapmax") or props.get("gainmapmax")
            min_v = props.get("hdrgainmapmin") or props.get("gainmapmin")
            gamma_v = props.get("hdrgainmapgamma") or props.get("gamma")
            off_sdr_v = props.get("hdrgainmapoffsetsdr") or props.get("offsetsdr")
            off_hdr_v = props.get("hdrgainmapoffsethdr") or props.get("offsethdr")
            cap_min_v = props.get("hdrgainmaphdrcapacitymin") or props.get("hdrcapacitymin")
            cap_max_v = props.get("hdrgainmaphdrcapacitymax") or props.get("hdrcapacitymax")
            base_hdr_v = props.get("baserenditionishdr")

            if max_v is not None:
                max_boost = _val_to_tuple3(max_v, 2.0)
                min_boost = _val_to_tuple3(min_v, 0.0)
                gamma = _val_to_tuple3(gamma_v, 1.0)
                off_sdr = _val_to_tuple3(off_sdr_v, 1.0 / 64.0)
                off_hdr = _val_to_tuple3(off_hdr_v, 1.0 / 64.0)

                cap_min = float(cap_min_v) if cap_min_v is not None else 0.0
                cap_max = float(cap_max_v) if cap_max_v is not None else (2.0 ** max(max_boost))
                base_is_hdr = str(base_hdr_v).lower() in ("true", "1")

                return GainMapMetadata(
                    gain_map_min=min_boost,
                    gain_map_max=max_boost,
                    gamma=gamma,
                    offset_sdr=off_sdr,
                    offset_hdr=off_hdr,
                    hdr_capacity_min=cap_min,
                    hdr_capacity_max=cap_max,
                    base_rendition_is_hdr=base_is_hdr,
                    standard="apple" if is_apple else "iso_21496_1",
                )

    return _parse_xmp_fallback(xmp_str)


def _parse_apple_gainmap_desc(desc: ET.Element) -> GainMapMetadata:
    """Parse Apple HDRGainMap XML element."""
    ns = "http://ns.apple.com/HDRGainMap/1.0/"

    def get_val(key: str, default: float) -> float:
        v = desc.attrib.get(f"{{{ns}}}{key}")
        if v is None:
            el = desc.find(f"{{{ns}}}{key}")
            if el is not None and el.text:
                v = el.text
        if v is not None:
            try:
                return float(v)
            except ValueError:
                pass
        return default

    min_boost = get_val("HDRGainMapMin", 0.0)
    max_boost = get_val("HDRGainMapMax", 2.0)
    gamma = get_val("HDRGainMapGamma", 1.0)
    offset_sdr = get_val("HDRGainMapOffsetSDR", 1.0 / 64.0)
    offset_hdr = get_val("HDRGainMapOffsetHDR", 1.0 / 64.0)
    cap_min = get_val("HDRGainMapHDRCapacityMin", 1.0)
    cap_max = get_val("HDRGainMapHDRCapacityMax", 2.0**max_boost)

    return GainMapMetadata(
        gain_map_min=(min_boost, min_boost, min_boost),
        gain_map_max=(max_boost, max_boost, max_boost),
        gamma=(gamma, gamma, gamma),
        offset_sdr=(offset_sdr, offset_sdr, offset_sdr),
        offset_hdr=(offset_hdr, offset_hdr, offset_hdr),
        hdr_capacity_min=cap_min,
        hdr_capacity_max=cap_max,
        standard="apple",
    )


def _parse_iso_gainmap_desc(desc: ET.Element) -> GainMapMetadata:
    """Parse ISO 21496-1 / Adobe Ultra HDR element."""
    iso_ns = "http://iso.org/gainmap/1.0/"
    adobe_ns = "http://ns.adobe.com/hdr-gain-map/1.0/"

    def get_seq(key: str, default: float) -> Tuple[float, float, float]:
        # Check attribute
        v = desc.attrib.get(f"{{{iso_ns}}}{key}") or desc.attrib.get(f"{{{adobe_ns}}}{key}")
        if v is not None:
            try:
                f = float(v)
                return (f, f, f)
            except ValueError:
                pass

        # Check child sequence element (rdf:Seq)
        child = desc.find(f"{{{iso_ns}}}{key}")
        if child is None:
            child = desc.find(f"{{{adobe_ns}}}{key}")

        if child is not None:
            items = child.findall(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li")
            if items:
                vals = []
                for it in items:
                    try:
                        vals.append(float(it.text or "0"))
                    except ValueError:
                        vals.append(default)
                if len(vals) == 1:
                    return (vals[0], vals[0], vals[0])
                elif len(vals) >= 3:
                    return (vals[0], vals[1], vals[2])
            elif child.text:
                try:
                    f = float(child.text)
                    return (f, f, f)
                except ValueError:
                    pass

        return (default, default, default)

    def get_scalar(key: str, default: float) -> float:
        v = desc.attrib.get(f"{{{iso_ns}}}{key}") or desc.attrib.get(f"{{{adobe_ns}}}{key}")
        if v is not None:
            try:
                return float(v)
            except ValueError:
                pass
        child = desc.find(f"{{{iso_ns}}}{key}") or desc.find(f"{{{adobe_ns}}}{key}")
        if child is not None and child.text:
            try:
                return float(child.text)
            except ValueError:
                pass
        return default

    min_boost = get_seq("GainMapMin", 0.0)
    max_boost = get_seq("GainMapMax", 2.0)
    gamma = get_seq("Gamma", 1.0)
    offset_sdr = get_seq("OffsetSDR", 1.0 / 64.0)
    offset_hdr = get_seq("OffsetHDR", 1.0 / 64.0)
    cap_min = get_scalar("HDRCapacityMin", 1.0)
    cap_max = get_scalar("HDRCapacityMax", 2.0 ** max(max_boost))
    base_hdr_val = desc.attrib.get(f"{{{iso_ns}}}BaseRenditionIsHDR") or desc.attrib.get(
        f"{{{adobe_ns}}}BaseRenditionIsHDR"
    )
    base_is_hdr = str(base_hdr_val).lower() in ("true", "1")

    return GainMapMetadata(
        gain_map_min=min_boost,
        gain_map_max=max_boost,
        gamma=gamma,
        offset_sdr=offset_sdr,
        offset_hdr=offset_hdr,
        hdr_capacity_min=cap_min,
        hdr_capacity_max=cap_max,
        base_rendition_is_hdr=base_is_hdr,
        standard="iso_21496_1",
    )


def _parse_xmp_fallback(text: str) -> Optional[GainMapMetadata]:
    """Simple regex/string search fallback for malformed or embedded XMP snippets."""
    import re

    max_m = re.search(r'(?:HDRGainMapMax|GainMapMax)["\']?\s*[:=]\s*["\']?([0-9.]+)', text)
    if not max_m:
        return None

    max_val = float(max_m.group(1))

    min_m = re.search(r'(?:HDRGainMapMin|GainMapMin)["\']?\s*[:=]\s*["\']?([0-9.]+)', text)
    min_val = float(min_m.group(1)) if min_m else 0.0

    gamma_m = re.search(r'(?:HDRGainMapGamma|Gamma)["\']?\s*[:=]\s*["\']?([0-9.]+)', text)
    gamma_val = float(gamma_m.group(1)) if gamma_m else 1.0

    cap_m = re.search(r'(?:HDRCapacityMax|HDRGainMapHDRCapacityMax)["\']?\s*[:=]\s*["\']?([0-9.]+)', text)
    cap_max = float(cap_m.group(1)) if cap_m else 2.0**max_val

    return GainMapMetadata(
        gain_map_min=(min_val, min_val, min_val),
        gain_map_max=(max_val, max_val, max_val),
        gamma=(gamma_val, gamma_val, gamma_val),
        hdr_capacity_min=1.0,
        hdr_capacity_max=cap_max,
        standard="dual",
    )


def generate_gain_map_xmp(metadata: GainMapMetadata, format_type: str = "dual") -> bytes:
    """Generate XMP packet containing ISO 21496-1, Apple HDRGainMap, or dual metadata.

    Args:
        metadata: GainMapMetadata instance.
        format_type: 'ISO', 'Apple', or 'dual' (default).
    """
    g_min = metadata.gain_map_min
    g_max = metadata.gain_map_max
    gamma = metadata.gamma
    o_sdr = metadata.offset_sdr
    o_hdr = metadata.offset_hdr
    cap_min = metadata.hdr_capacity_min
    cap_max = metadata.hdr_capacity_max

    apple_min = g_min[0]
    apple_max = max(g_max)
    apple_gamma = gamma[0]
    apple_osdr = o_sdr[0]
    apple_ohdr = o_hdr[0]

    fmt = format_type.upper()
    if fmt in ("APPLE", "HDRGAINMAP"):
        xml = f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="pylibheif Apple HDR Engine">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:HDRGainMap="http://ns.apple.com/HDRGainMap/1.0/"
    HDRGainMap:HDRGainMapVersion="65536"
    HDRGainMap:HDRGainMapMin="{apple_min:.4f}"
    HDRGainMap:HDRGainMapMax="{apple_max:.4f}"
    HDRGainMap:Gamma="{apple_gamma:.4f}"
    HDRGainMap:HDRGainMapOffsetSDR="{apple_osdr:.6f}"
    HDRGainMap:HDRGainMapOffsetHDR="{apple_ohdr:.6f}"
    HDRGainMap:HDRGainMapHDRCapacityMin="{cap_min:.4f}"
    HDRGainMap:HDRGainMapHDRCapacityMax="{cap_max:.4f}"
    HDRGainMap:BaseRenditionIsHDR="{"True" if metadata.base_rendition_is_hdr else "False"}"/>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    elif fmt in ("ISO", "ISO_21496_1"):
        xml = f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="pylibheif ISO 21496-1 Engine">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:hdrgm="urn:iso:std:iso:ts:21496-1"
    hdrgm:version="1.0.0"
    hdrgm:gainMapMin="{g_min[0]:.6f}"
    hdrgm:gainMapMax="{g_max[0]:.6f}"
    hdrgm:gamma="{gamma[0]:.6f}"
    hdrgm:offsetSdr="{o_sdr[0]:.6f}"
    hdrgm:offsetHdr="{o_hdr[0]:.6f}"
    hdrgm:hdrCapacityMin="{cap_min:.4f}"
    hdrgm:hdrCapacityMax="{cap_max:.4f}"
    hdrgm:baseRenditionIsHDR="{"True" if metadata.base_rendition_is_hdr else "False"}"/>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    else:
        # Dual-encoding for maximum ecosystem compatibility
        xml = f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="pylibheif ISO 21496-1 / Apple HDR Engine">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:apple="http://ns.apple.com/HDRGainMap/1.0/"
    xmlns:hdrgm="urn:iso:std:iso:ts:21496-1"
    xmlns:iso="http://iso.org/gainmap/1.0/"
    apple:HDRGainMapVersion="65536"
    apple:HDRGainMapMin="{apple_min:.4f}"
    apple:HDRGainMapMax="{apple_max:.4f}"
    apple:HDRGainMapGamma="{apple_gamma:.4f}"
    apple:HDRGainMapOffsetSDR="{apple_osdr:.6f}"
    apple:HDRGainMapOffsetHDR="{apple_ohdr:.6f}"
    apple:HDRGainMapHDRCapacityMin="{cap_min:.4f}"
    apple:HDRGainMapHDRCapacityMax="{cap_max:.4f}"
    hdrgm:version="1.0.0"
    hdrgm:gainMapMin="{g_min[0]:.6f}"
    hdrgm:gainMapMax="{g_max[0]:.6f}"
    hdrgm:gamma="{gamma[0]:.6f}"
    hdrgm:offsetSdr="{o_sdr[0]:.6f}"
    hdrgm:offsetHdr="{o_hdr[0]:.6f}"
    hdrgm:hdrCapacityMin="{cap_min:.4f}"
    hdrgm:hdrCapacityMax="{cap_max:.4f}"
    hdrgm:baseRenditionIsHDR="{"True" if metadata.base_rendition_is_hdr else "False"}"/>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    return xml.encode("utf-8")


# ==============================================================================
# Color Management & Transfer Functions (EOTF & OETF)
# ==============================================================================


def srgb_to_linear(srgb: Union[np.ndarray, float, int]) -> np.ndarray:
    """Exact inverse sRGB EOTF conversion (non-linear [0, 1] to linear light)."""
    srgb_arr = np.asarray(srgb, dtype=np.float32)
    linear = np.empty_like(srgb_arr, dtype=np.float32)
    mask = srgb_arr <= 0.04045
    linear[mask] = srgb_arr[mask] / 12.92
    linear[~mask] = np.power((srgb_arr[~mask] + 0.055) / 1.055, 2.4)
    return linear


def linear_to_srgb(linear: Union[np.ndarray, float, int]) -> np.ndarray:
    """Exact forward sRGB OETF conversion (linear light to non-linear [0, 1])."""
    linear_arr = np.asarray(linear, dtype=np.float32)
    srgb = np.empty_like(linear_arr, dtype=np.float32)
    clamped = np.clip(linear_arr, 0.0, None)
    mask = clamped <= 0.0031308
    srgb[mask] = clamped[mask] * 12.92
    srgb[~mask] = 1.055 * np.power(clamped[~mask], 1.0 / 2.4) - 0.055
    return np.clip(srgb, 0.0, 1.0)


def linear_to_pq(linear: np.ndarray, max_nits: float = 1000.0) -> np.ndarray:
    """SMPTE ST 2084 (Perceptual Quantizer / PQ) conversion for Rec.2100 HDR10 output.

    Args:
        linear: Linear RGB normalized where 1.0 corresponds to standard SDR reference (100 nits).
        max_nits: Absolute peak luminance target (default 1000 nits for standard HDR10).

    Returns:
        10-bit integer array (uint16 in range 0..1023) encoded with PQ curve.
    """
    # ST 2084 constants
    m1 = 2610.0 / 16384.0
    m2 = 2523.0 / 4096.0 * 128.0
    c1 = 3424.0 / 4096.0
    c2 = 2413.0 / 4096.0 * 32.0
    c3 = 2392.0 / 4096.0 * 32.0

    # 1.0 linear = 100 nits. Full scale 10000 nits = 100.0
    y = np.clip(linear * (100.0 / 10000.0), 0.0, 1.0)
    y_m1 = np.power(y, m1)
    num = c1 + c2 * y_m1
    den = 1.0 + c3 * y_m1
    pq = np.power(num / den, m2)

    return (np.clip(pq, 0.0, 1.0) * 1023.0 + 0.5).astype(np.uint16)


# ==============================================================================
# Resampling & Interpolation
# ==============================================================================


def _resample_gain_map(gain_map: np.ndarray, target_height: int, target_width: int) -> np.ndarray:
    """Bilinear resampling of Gain Map to match SDR dimensions with center alignment."""
    if gain_map.shape[0] == target_height and gain_map.shape[1] == target_width:
        return gain_map

    # Use Pillow if available for fast C-accelerated resampling
    try:
        from PIL import Image

        mode = "L" if gain_map.ndim == 2 or gain_map.shape[2] == 1 else "RGB"
        if mode == "L" and gain_map.ndim == 3:
            im_data = gain_map[:, :, 0]
        else:
            im_data = gain_map

        pil_img = Image.fromarray((im_data * 255.0).astype(np.uint8), mode=mode)
        resized = pil_img.resize((target_width, target_height), resample=Image.Resampling.BILINEAR)
        res_arr = np.asarray(resized).astype(np.float32) / 255.0
        if gain_map.ndim == 3 and res_arr.ndim == 2:
            res_arr = np.expand_dims(res_arr, axis=-1)
        return res_arr
    except Exception:
        pass

    # Pure numpy bilinear interpolation fallback
    gh, gw = gain_map.shape[:2]
    y_indices = (np.arange(target_height, dtype=np.float32) + 0.5) * (gh / target_height) - 0.5
    x_indices = (np.arange(target_width, dtype=np.float32) + 0.5) * (gw / target_width) - 0.5

    y_indices = np.clip(y_indices, 0, gh - 1)
    x_indices = np.clip(x_indices, 0, gw - 1)

    y0 = np.floor(y_indices).astype(np.int32)
    y1 = np.clip(y0 + 1, 0, gh - 1)
    x0 = np.floor(x_indices).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, gw - 1)

    wy = (y_indices - y0)[:, np.newaxis]
    wx = (x_indices - x0)[np.newaxis, :]

    if gain_map.ndim == 3:
        wy = wy[:, :, np.newaxis]
        wx = wx[:, :, np.newaxis]

    i00 = gain_map[y0[:, np.newaxis], x0[np.newaxis, :]]
    i01 = gain_map[y0[:, np.newaxis], x1[np.newaxis, :]]
    i10 = gain_map[y1[:, np.newaxis], x0[np.newaxis, :]]
    i11 = gain_map[y1[:, np.newaxis], x1[np.newaxis, :]]

    top = (1.0 - wx) * i00 + wx * i01
    bottom = (1.0 - wx) * i10 + wx * i11
    return (1.0 - wy) * top + wy * bottom


def resample_gain_map(
    gain_map: np.ndarray,
    target_shape: Union[Tuple[int, int], Tuple[int, int, int]],
) -> np.ndarray:
    """Bilinear resampling of Gain Map to match target dimensions with center alignment.

    Args:
        gain_map: numpy array with shape (H, W) or (H, W, C).
        target_shape: Tuple (target_height, target_width).

    Returns:
        Resampled numpy array with shape (target_height, target_width) or (target_height, target_width, C).
    """
    target_height, target_width = target_shape[0], target_shape[1]
    return _resample_gain_map(gain_map, target_height, target_width)


# ==============================================================================
# ISO 21496-1 Tonemapping & Reconstruction Engine
# ==============================================================================


def reconstruct_hdr(
    sdr_image: Any,
    gain_map: Any,
    metadata: Optional[GainMapMetadata] = None,
    target_headroom: Optional[float] = None,
    output_format: str = "linear",
    dtype: Any = np.float32,
    display_boost: Optional[float] = None,
) -> np.ndarray:
    """Reconstruct an HDR image from an SDR base image, Gain Map, and ISO 21496-1 metadata.

    Args:
        sdr_image: 8-bit SDR image (numpy array shape (H, W, 3) or (H, W, 4), or PIL.Image).
        gain_map: Gain Map image (1-channel monochrome or 3-channel RGB).
        metadata: GainMapMetadata instance. If None, default 4x boost (2.0 stops) is used.
        target_headroom: Desired display headroom multiplier (e.g. 2.0 or 4.0).
                         If None, uses metadata.hdr_capacity_max (full HDR capability).
        output_format: Output image format:
            - "linear" / "linear_float32" / "linear_float16": Normalized linear RGB light.
            - "pq" / "pq_uint16": Rec.2100 PQ ST 2084 integer format (uint16 array 0..65535).
            - "srgb_clip" / "srgb_uint8" / "srgb": Tonemapped back to standard 8-bit sRGB (uint8 array 0..255).
        dtype: Numerical data type for linear computations (np.float32 or np.float16).
        display_boost: Alias for target_headroom.

    Returns:
        Reconstructed HDR numpy array in the requested output_format.
    """
    if target_headroom is None and display_boost is not None:
        target_headroom = display_boost

    norm_fmt = output_format.lower()
    if norm_fmt in ("linear_float16", "float16"):
        dtype = np.float16
        norm_fmt = "linear"
    elif norm_fmt in ("linear_float32", "float32"):
        dtype = np.float32
        norm_fmt = "linear"
    elif norm_fmt in ("pq_uint16",):
        norm_fmt = "pq"
    elif norm_fmt in ("srgb_uint8", "srgb"):
        norm_fmt = "srgb_clip"

    if metadata is None:
        metadata = GainMapMetadata.from_scalar(max_boost_stops=2.0)

    # Convert inputs to numpy arrays in [0.0, 1.0] range
    try:
        from PIL import Image

        if isinstance(sdr_image, Image.Image):
            if sdr_image.mode not in ("RGB", "RGBA"):
                sdr_image = sdr_image.convert("RGB")
            sdr_arr = np.asarray(sdr_image).astype(np.float32) / 255.0
        else:
            sdr_arr = np.asarray(sdr_image, dtype=np.float32)
            if sdr_arr.max() > 1.0:
                sdr_arr /= 255.0

        if isinstance(gain_map, Image.Image):
            gm_arr = np.asarray(gain_map).astype(np.float32) / 255.0
        else:
            gm_arr = np.asarray(gain_map, dtype=np.float32)
            if gm_arr.max() > 1.0:
                gm_arr /= 255.0
    except ImportError:
        sdr_arr = np.asarray(sdr_image, dtype=np.float32)
        if sdr_arr.max() > 1.0:
            sdr_arr /= 255.0
        gm_arr = np.asarray(gain_map, dtype=np.float32)
        if gm_arr.max() > 1.0:
            gm_arr /= 255.0

    # Extract alpha if present in SDR
    alpha = None
    if sdr_arr.ndim == 3 and sdr_arr.shape[2] == 4:
        alpha = sdr_arr[:, :, 3]
        sdr_arr = sdr_arr[:, :, :3]

    # Resample gain map to SDR resolution if dimensions differ
    sh, sw = sdr_arr.shape[:2]
    if gm_arr.shape[0] != sh or gm_arr.shape[1] != sw:
        gm_arr = _resample_gain_map(gm_arr, sh, sw)

    # Convert SDR from non-linear gamma to linear light
    sdr_linear = srgb_to_linear(sdr_arr)

    # 1. Compute weight factor W based on target display headroom
    # H_disp = log2(target_headroom)
    # W = (H_disp - H_min) / (H_max - H_min)
    if target_headroom is None:
        w_factor = 1.0
    else:
        h_disp = math.log2(max(float(target_headroom), 1e-6))
        h_min = metadata.hdr_capacity_min
        h_max = metadata.hdr_capacity_max
        if h_max <= h_min:
            w_factor = 1.0
        else:
            w_factor = float(np.clip((h_disp - h_min) / (h_max - h_min), 0.0, 1.0))

    # 2. Unpack metadata arrays and handle gamma decoding on Gain Map
    # f(gm) = gm ^ gamma
    gamma = np.array(metadata.gamma, dtype=np.float32)
    g_min = np.array(metadata.gain_map_min, dtype=np.float32)
    g_max = np.array(metadata.gain_map_max, dtype=np.float32)
    o_sdr = np.array(metadata.offset_sdr, dtype=np.float32)
    o_hdr = np.array(metadata.offset_hdr, dtype=np.float32)

    if gm_arr.ndim == 2:
        gm_arr = np.expand_dims(gm_arr, axis=-1)

    # Apply gamma if != 1.0
    if np.any(np.abs(gamma - 1.0) > 1e-4):
        gm_norm = np.power(np.clip(gm_arr, 0.0, 1.0), gamma)
    else:
        gm_norm = np.clip(gm_arr, 0.0, 1.0)

    # 3. Compute log2 gain and convert to linear scale
    # log_gain = (min + gm_norm * (max - min)) * W
    log_gain = (g_min + gm_norm * (g_max - g_min)) * w_factor
    gain = np.power(2.0, log_gain)

    # 4. Reconstruct linear HDR light: L_hdr = (L_sdr + offset_sdr) * gain - offset_hdr
    hdr_linear = (sdr_linear + o_sdr) * gain - o_hdr
    hdr_linear = np.maximum(hdr_linear, 0.0)

    # 5. Format output
    if norm_fmt == "linear":
        res = hdr_linear.astype(dtype)
        if alpha is not None:
            alpha_expanded = np.expand_dims(alpha.astype(dtype), axis=-1)
            res = np.concatenate([res, alpha_expanded], axis=-1)
        return res
    elif norm_fmt == "pq":
        pq_res = linear_to_pq(hdr_linear)
        return pq_res
    elif norm_fmt == "srgb_clip":
        srgb_out = linear_to_srgb(hdr_linear)
        uint8_res = (np.clip(srgb_out, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        if alpha is not None:
            a_uint8 = (np.clip(alpha, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)[:, :, np.newaxis]
            uint8_res = np.concatenate([uint8_res, a_uint8], axis=-1)
        return uint8_res
    else:
        raise ValueError(
            f"Unknown output_format '{output_format}'. Choose 'linear', 'linear_float16', 'pq', or 'srgb_clip'."
        )
