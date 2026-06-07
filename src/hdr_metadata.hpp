#pragma once
#include <utility>

namespace pylibheif {

struct HeifContentLightLevel {
    uint16_t max_content_light_level;
    uint16_t max_pic_average_light_level;
};

struct HeifMasteringDisplayColourVolume {
    std::pair<float, float> red_primary;
    std::pair<float, float> green_primary;
    std::pair<float, float> blue_primary;
    std::pair<float, float> white_point;
    double max_luminance;
    double min_luminance;
};

struct HeifAmbientViewingEnvironment {
    double ambient_illumination;
    std::pair<float, float> ambient_light;
};

}  // namespace pylibheif
