#pragma once
#include <libheif/heif.h>

namespace pylibheif {

struct HeifColorProfileNclx {
    heif_color_primaries color_primaries;
    heif_transfer_characteristics transfer_characteristics;
    heif_matrix_coefficients matrix_coefficients;
    bool full_range_flag;

    // Decoded coordinates (read-only info)
    float color_primary_red_x = 0.0f;
    float color_primary_red_y = 0.0f;
    float color_primary_green_x = 0.0f;
    float color_primary_green_y = 0.0f;
    float color_primary_blue_x = 0.0f;
    float color_primary_blue_y = 0.0f;
    float color_primary_white_x = 0.0f;
    float color_primary_white_y = 0.0f;

    HeifColorProfileNclx()
        : color_primaries(heif_color_primaries_unspecified),
          transfer_characteristics(heif_transfer_characteristic_unspecified),
          matrix_coefficients(heif_matrix_coefficients_unspecified),
          full_range_flag(false) {}

    HeifColorProfileNclx(heif_color_primaries cp, heif_transfer_characteristics tc,
                         heif_matrix_coefficients mc, bool fr)
        : color_primaries(cp),
          transfer_characteristics(tc),
          matrix_coefficients(mc),
          full_range_flag(fr) {}
};

}  // namespace pylibheif
