# Depth Map & Auxiliary API

Domain entities, physical metric depth conversions (ISO/IEC 23008-12 / ITU-T H.265), colormaps, and auxiliary image extractors.

---

## `DepthMap`

::: pylibheif.DepthMap
    options:
      members:
        - info
        - handle
        - master_handle
        - representation_type
        - decode
        - to_metric_depth
        - to_pillow

---

## `AsyncDepthMap`

::: pylibheif.AsyncDepthMap
    options:
      members:
        - info
        - handle
        - master_handle
        - decode
        - to_metric_depth
        - to_pillow

---

## `DepthRepresentationType`

::: pylibheif.DepthRepresentationType

---

## Top-Level Extraction Helpers

::: pylibheif.extract_depth_map

::: pylibheif.extract_portrait_matte
