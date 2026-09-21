#include "gain_map_accel.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <future>
#include <thread>
#include <vector>

namespace pylibheif {

namespace {

// Precomputed 256-element float32 lookup table for exact inverse sRGB EOTF
struct SrgbLut {
    std::array<float, 256> table;
    SrgbLut() {
        for (int i = 0; i < 256; ++i) {
            float v = i / 255.0f;
            if (v <= 0.04045f) {
                table[i] = v / 12.92f;
            } else {
                table[i] = std::pow((v + 0.055f) / 1.055f, 2.4f);
            }
        }
    }
};

const SrgbLut g_srgb_lut;

inline float linear_to_srgb_val(float linear) {
    if (linear <= 0.0f) return 0.0f;
    if (linear >= 1.0f) return 1.0f;
    if (linear <= 0.0031308f) {
        return linear * 12.92f;
    }
    return 1.055f * std::pow(linear, 1.0f / 2.4f) - 0.055f;
}

inline uint16_t linear_to_pq_val(float linear) {
    if (linear <= 0.0f) return 0;
    // 1.0 linear = 100 nits. Full scale 10000 nits = 100.0
    float y = std::min(linear * (100.0f / 10000.0f), 1.0f);
    float y_m1 = std::pow(y, 2610.0f / 16384.0f);
    float num = (3424.0f / 4096.0f) + (2413.0f / 4096.0f * 32.0f) * y_m1;
    float den = 1.0f + (2392.0f / 4096.0f * 32.0f) * y_m1;
    float pq = std::pow(num / den, 2523.0f / 4096.0f * 128.0f);
    if (pq >= 1.0f) return 1023;
    if (pq <= 0.0f) return 0;
    return static_cast<uint16_t>(pq * 1023.0f + 0.5f);
}

template <typename WorkerFunc>
void parallel_for_rows(size_t height, WorkerFunc&& func) {
    size_t num_threads =
        std::max<size_t>(1, std::min<size_t>(std::thread::hardware_concurrency(), 16));
    if (height < 64 || num_threads <= 1) {
        func(0, height);
        return;
    }

    size_t chunk_size = (height + num_threads - 1) / num_threads;
    std::vector<std::future<void>> futures;
    futures.reserve(num_threads);

    for (size_t t = 0; t < num_threads; ++t) {
        size_t start_y = t * chunk_size;
        size_t end_y = std::min(start_y + chunk_size, height);
        if (start_y < end_y) {
            futures.push_back(std::async(std::launch::async,
                                         [start_y, end_y, &func]() { func(start_y, end_y); }));
        }
    }

    for (auto& f : futures) {
        f.get();
    }
}

}  // namespace

bool reconstruct_hdr_linear_cpp(nb::ndarray<const uint8_t, nb::c_contig> sdr_arr,
                                nb::ndarray<const uint8_t, nb::c_contig> gm_arr,
                                nb::ndarray<float, nb::c_contig> out_arr,
                                const GainMapParams& params) {
    if (sdr_arr.ndim() != 3 || out_arr.ndim() != 3) {
        return false;
    }

    size_t height = sdr_arr.shape(0);
    size_t width = sdr_arr.shape(1);
    size_t sdr_channels = sdr_arr.shape(2);
    size_t out_channels = out_arr.shape(2);

    if (sdr_channels < 3 || out_channels < 3) {
        return false;
    }

    // Check dimensions match
    if (out_arr.shape(0) != height || out_arr.shape(1) != width) {
        return false;
    }
    if (gm_arr.shape(0) != height || gm_arr.shape(1) != width) {
        return false;  // Gain map must be pre-resampled to base dimensions
    }

    size_t gm_channels = (gm_arr.ndim() == 3) ? gm_arr.shape(2) : 1;
    bool is_mono = params.is_monochrome || (gm_channels == 1);

    const uint8_t* sdr_ptr = sdr_arr.data();
    const uint8_t* gm_ptr = gm_arr.data();
    float* out_ptr = out_arr.data();

    const auto& lut = g_srgb_lut.table;
    bool apply_gamma = std::abs(params.gamma[0] - 1.0f) > 1e-4f ||
                       std::abs(params.gamma[1] - 1.0f) > 1e-4f ||
                       std::abs(params.gamma[2] - 1.0f) > 1e-4f;

    // Release GIL for multi-threading
    nb::gil_scoped_release release;

    parallel_for_rows(height, [&](size_t start_y, size_t end_y) {
        for (size_t y = start_y; y < end_y; ++y) {
            size_t sdr_row_offset = y * width * sdr_channels;
            size_t gm_row_offset = y * width * gm_channels;
            size_t out_row_offset = y * width * out_channels;

            for (size_t x = 0; x < width; ++x) {
                size_t sdr_idx = sdr_row_offset + x * sdr_channels;
                size_t gm_idx = gm_row_offset + x * gm_channels;
                size_t out_idx = out_row_offset + x * out_channels;

                uint8_t r_u8 = sdr_ptr[sdr_idx + 0];
                uint8_t g_u8 = sdr_ptr[sdr_idx + 1];
                uint8_t b_u8 = sdr_ptr[sdr_idx + 2];

                float lin_r = lut[r_u8];
                float lin_g = lut[g_u8];
                float lin_b = lut[b_u8];

                if (is_mono) {
                    float gm_norm = gm_ptr[gm_idx] * (1.0f / 255.0f);
                    if (apply_gamma) {
                        gm_norm = std::pow(gm_norm, params.gamma[0]);
                    }
                    float log_gain = (params.gain_map_min[0] +
                                      gm_norm * (params.gain_map_max[0] - params.gain_map_min[0])) *
                                     params.w_factor;
                    float gain = std::exp2(log_gain);

                    out_ptr[out_idx + 0] = std::max(
                        0.0f, (lin_r + params.offset_sdr[0]) * gain - params.offset_hdr[0]);
                    out_ptr[out_idx + 1] = std::max(
                        0.0f, (lin_g + params.offset_sdr[1]) * gain - params.offset_hdr[1]);
                    out_ptr[out_idx + 2] = std::max(
                        0.0f, (lin_b + params.offset_sdr[2]) * gain - params.offset_hdr[2]);
                } else {
                    for (int c = 0; c < 3; ++c) {
                        float gm_norm = gm_ptr[gm_idx + c] * (1.0f / 255.0f);
                        if (apply_gamma) {
                            gm_norm = std::pow(gm_norm, params.gamma[c]);
                        }
                        float log_gain =
                            (params.gain_map_min[c] +
                             gm_norm * (params.gain_map_max[c] - params.gain_map_min[c])) *
                            params.w_factor;
                        float gain = std::exp2(log_gain);
                        float lin_c = (c == 0) ? lin_r : (c == 1 ? lin_g : lin_b);
                        out_ptr[out_idx + c] = std::max(
                            0.0f, (lin_c + params.offset_sdr[c]) * gain - params.offset_hdr[c]);
                    }
                }

                // Copy alpha if 4 channels
                if (sdr_channels >= 4 && out_channels >= 4) {
                    out_ptr[out_idx + 3] = sdr_ptr[sdr_idx + 3] * (1.0f / 255.0f);
                }
            }
        }
    });

    return true;
}

bool reconstruct_hdr_srgb_cpp(nb::ndarray<const uint8_t, nb::c_contig> sdr_arr,
                              nb::ndarray<const uint8_t, nb::c_contig> gm_arr,
                              nb::ndarray<uint8_t, nb::c_contig> out_arr,
                              const GainMapParams& params) {
    if (sdr_arr.ndim() != 3 || out_arr.ndim() != 3) {
        return false;
    }

    size_t height = sdr_arr.shape(0);
    size_t width = sdr_arr.shape(1);
    size_t sdr_channels = sdr_arr.shape(2);
    size_t out_channels = out_arr.shape(2);

    if (sdr_channels < 3 || out_channels < 3) {
        return false;
    }
    if (out_arr.shape(0) != height || out_arr.shape(1) != width) {
        return false;
    }
    if (gm_arr.shape(0) != height || gm_arr.shape(1) != width) {
        return false;
    }

    size_t gm_channels = (gm_arr.ndim() == 3) ? gm_arr.shape(2) : 1;
    bool is_mono = params.is_monochrome || (gm_channels == 1);

    const uint8_t* sdr_ptr = sdr_arr.data();
    const uint8_t* gm_ptr = gm_arr.data();
    uint8_t* out_ptr = out_arr.data();

    const auto& lut = g_srgb_lut.table;
    bool apply_gamma = std::abs(params.gamma[0] - 1.0f) > 1e-4f ||
                       std::abs(params.gamma[1] - 1.0f) > 1e-4f ||
                       std::abs(params.gamma[2] - 1.0f) > 1e-4f;

    // Release GIL for multi-threading
    nb::gil_scoped_release release;

    parallel_for_rows(height, [&](size_t start_y, size_t end_y) {
        for (size_t y = start_y; y < end_y; ++y) {
            size_t sdr_row_offset = y * width * sdr_channels;
            size_t gm_row_offset = y * width * gm_channels;
            size_t out_row_offset = y * width * out_channels;

            for (size_t x = 0; x < width; ++x) {
                size_t sdr_idx = sdr_row_offset + x * sdr_channels;
                size_t gm_idx = gm_row_offset + x * gm_channels;
                size_t out_idx = out_row_offset + x * out_channels;

                uint8_t r_u8 = sdr_ptr[sdr_idx + 0];
                uint8_t g_u8 = sdr_ptr[sdr_idx + 1];
                uint8_t b_u8 = sdr_ptr[sdr_idx + 2];

                float lin_r = lut[r_u8];
                float lin_g = lut[g_u8];
                float lin_b = lut[b_u8];

                float hdr_r = 0.0f, hdr_g = 0.0f, hdr_b = 0.0f;

                if (is_mono) {
                    float gm_norm = gm_ptr[gm_idx] * (1.0f / 255.0f);
                    if (apply_gamma) {
                        gm_norm = std::pow(gm_norm, params.gamma[0]);
                    }
                    float log_gain = (params.gain_map_min[0] +
                                      gm_norm * (params.gain_map_max[0] - params.gain_map_min[0])) *
                                     params.w_factor;
                    float gain = std::exp2(log_gain);

                    hdr_r = std::max(0.0f,
                                     (lin_r + params.offset_sdr[0]) * gain - params.offset_hdr[0]);
                    hdr_g = std::max(0.0f,
                                     (lin_g + params.offset_sdr[1]) * gain - params.offset_hdr[1]);
                    hdr_b = std::max(0.0f,
                                     (lin_b + params.offset_sdr[2]) * gain - params.offset_hdr[2]);
                } else {
                    float gains[3];
                    for (int c = 0; c < 3; ++c) {
                        float gm_norm = gm_ptr[gm_idx + c] * (1.0f / 255.0f);
                        if (apply_gamma) {
                            gm_norm = std::pow(gm_norm, params.gamma[c]);
                        }
                        float log_gain =
                            (params.gain_map_min[c] +
                             gm_norm * (params.gain_map_max[c] - params.gain_map_min[c])) *
                            params.w_factor;
                        gains[c] = std::exp2(log_gain);
                    }
                    hdr_r = std::max(
                        0.0f, (lin_r + params.offset_sdr[0]) * gains[0] - params.offset_hdr[0]);
                    hdr_g = std::max(
                        0.0f, (lin_g + params.offset_sdr[1]) * gains[1] - params.offset_hdr[1]);
                    hdr_b = std::max(
                        0.0f, (lin_b + params.offset_sdr[2]) * gains[2] - params.offset_hdr[2]);
                }

                out_ptr[out_idx + 0] =
                    static_cast<uint8_t>(linear_to_srgb_val(hdr_r) * 255.0f + 0.5f);
                out_ptr[out_idx + 1] =
                    static_cast<uint8_t>(linear_to_srgb_val(hdr_g) * 255.0f + 0.5f);
                out_ptr[out_idx + 2] =
                    static_cast<uint8_t>(linear_to_srgb_val(hdr_b) * 255.0f + 0.5f);

                if (sdr_channels >= 4 && out_channels >= 4) {
                    out_ptr[out_idx + 3] = sdr_ptr[sdr_idx + 3];
                }
            }
        }
    });

    return true;
}

bool reconstruct_hdr_pq_cpp(nb::ndarray<const uint8_t, nb::c_contig> sdr_arr,
                            nb::ndarray<const uint8_t, nb::c_contig> gm_arr,
                            nb::ndarray<uint16_t, nb::c_contig> out_arr,
                            const GainMapParams& params) {
    if (sdr_arr.ndim() != 3 || out_arr.ndim() != 3) {
        return false;
    }

    size_t height = sdr_arr.shape(0);
    size_t width = sdr_arr.shape(1);
    size_t sdr_channels = sdr_arr.shape(2);
    size_t out_channels = out_arr.shape(2);

    if (sdr_channels < 3 || out_channels < 3) {
        return false;
    }
    if (out_arr.shape(0) != height || out_arr.shape(1) != width) {
        return false;
    }
    if (gm_arr.shape(0) != height || gm_arr.shape(1) != width) {
        return false;
    }

    size_t gm_channels = (gm_arr.ndim() == 3) ? gm_arr.shape(2) : 1;
    bool is_mono = params.is_monochrome || (gm_channels == 1);

    const uint8_t* sdr_ptr = sdr_arr.data();
    const uint8_t* gm_ptr = gm_arr.data();
    uint16_t* out_ptr = out_arr.data();

    const auto& lut = g_srgb_lut.table;
    bool apply_gamma = std::abs(params.gamma[0] - 1.0f) > 1e-4f ||
                       std::abs(params.gamma[1] - 1.0f) > 1e-4f ||
                       std::abs(params.gamma[2] - 1.0f) > 1e-4f;

    // Release GIL for multi-threading
    nb::gil_scoped_release release;

    parallel_for_rows(height, [&](size_t start_y, size_t end_y) {
        for (size_t y = start_y; y < end_y; ++y) {
            size_t sdr_row_offset = y * width * sdr_channels;
            size_t gm_row_offset = y * width * gm_channels;
            size_t out_row_offset = y * width * out_channels;

            for (size_t x = 0; x < width; ++x) {
                size_t sdr_idx = sdr_row_offset + x * sdr_channels;
                size_t gm_idx = gm_row_offset + x * gm_channels;
                size_t out_idx = out_row_offset + x * out_channels;

                uint8_t r_u8 = sdr_ptr[sdr_idx + 0];
                uint8_t g_u8 = sdr_ptr[sdr_idx + 1];
                uint8_t b_u8 = sdr_ptr[sdr_idx + 2];

                float lin_r = lut[r_u8];
                float lin_g = lut[g_u8];
                float lin_b = lut[b_u8];

                float hdr_r = 0.0f, hdr_g = 0.0f, hdr_b = 0.0f;

                if (is_mono) {
                    float gm_norm = gm_ptr[gm_idx] * (1.0f / 255.0f);
                    if (apply_gamma) {
                        gm_norm = std::pow(gm_norm, params.gamma[0]);
                    }
                    float log_gain = (params.gain_map_min[0] +
                                      gm_norm * (params.gain_map_max[0] - params.gain_map_min[0])) *
                                     params.w_factor;
                    float gain = std::exp2(log_gain);

                    hdr_r = std::max(0.0f,
                                     (lin_r + params.offset_sdr[0]) * gain - params.offset_hdr[0]);
                    hdr_g = std::max(0.0f,
                                     (lin_g + params.offset_sdr[1]) * gain - params.offset_hdr[1]);
                    hdr_b = std::max(0.0f,
                                     (lin_b + params.offset_sdr[2]) * gain - params.offset_hdr[2]);
                } else {
                    float gains[3];
                    for (int c = 0; c < 3; ++c) {
                        float gm_norm = gm_ptr[gm_idx + c] * (1.0f / 255.0f);
                        if (apply_gamma) {
                            gm_norm = std::pow(gm_norm, params.gamma[c]);
                        }
                        float log_gain =
                            (params.gain_map_min[c] +
                             gm_norm * (params.gain_map_max[c] - params.gain_map_min[c])) *
                            params.w_factor;
                        gains[c] = std::exp2(log_gain);
                    }
                    hdr_r = std::max(
                        0.0f, (lin_r + params.offset_sdr[0]) * gains[0] - params.offset_hdr[0]);
                    hdr_g = std::max(
                        0.0f, (lin_g + params.offset_sdr[1]) * gains[1] - params.offset_hdr[1]);
                    hdr_b = std::max(
                        0.0f, (lin_b + params.offset_sdr[2]) * gains[2] - params.offset_hdr[2]);
                }

                out_ptr[out_idx + 0] = linear_to_pq_val(hdr_r);
                out_ptr[out_idx + 1] = linear_to_pq_val(hdr_g);
                out_ptr[out_idx + 2] = linear_to_pq_val(hdr_b);

                if (sdr_channels >= 4 && out_channels >= 4) {
                    out_ptr[out_idx + 3] = static_cast<uint16_t>(sdr_ptr[sdr_idx + 3]) << 2;
                }
            }
        }
    });

    return true;
}

}  // namespace pylibheif
