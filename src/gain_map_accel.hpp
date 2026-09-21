#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include <cstdint>

namespace nb = nanobind;

namespace pylibheif {

struct GainMapParams {
    float gain_map_min[3];
    float gain_map_max[3];
    float gamma[3];
    float offset_sdr[3];
    float offset_hdr[3];
    float w_factor;
    bool is_monochrome;
};

// Reconstruct HDR to linear float32
bool reconstruct_hdr_linear_cpp(nb::ndarray<const uint8_t, nb::c_contig> sdr_arr,
                                nb::ndarray<const uint8_t, nb::c_contig> gm_arr,
                                nb::ndarray<float, nb::c_contig> out_arr,
                                const GainMapParams& params);

// Reconstruct HDR to tonemapped sRGB uint8 (srgb_clip)
bool reconstruct_hdr_srgb_cpp(nb::ndarray<const uint8_t, nb::c_contig> sdr_arr,
                              nb::ndarray<const uint8_t, nb::c_contig> gm_arr,
                              nb::ndarray<uint8_t, nb::c_contig> out_arr,
                              const GainMapParams& params);

// Reconstruct HDR to Rec.2100 PQ uint16 (HDR10 ST 2084)
bool reconstruct_hdr_pq_cpp(nb::ndarray<const uint8_t, nb::c_contig> sdr_arr,
                            nb::ndarray<const uint8_t, nb::c_contig> gm_arr,
                            nb::ndarray<uint16_t, nb::c_contig> out_arr,
                            const GainMapParams& params);

}  // namespace pylibheif
