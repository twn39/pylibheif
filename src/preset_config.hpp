#pragma once

#include <algorithm>
#include <cctype>
#include <string>

namespace pylibheif {

struct PresetMappings {
    static std::string normalize_preset(const std::string& preset) {
        std::string p = preset;
        std::transform(p.begin(), p.end(), p.begin(),
                       [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
        return p;
    }

    static std::string map_x265_preset(const std::string& p) {
        if (p == "ultrafast") return "ultrafast";
        if (p == "fast") return "fast";
        if (p == "balanced") return "medium";
        if (p == "quality") return "slow";
        return p;
    }

    static int map_aom_speed(const std::string& p) {
        if (p == "ultrafast") return 8;
        if (p == "fast") return 6;
        if (p == "balanced") return 6;
        if (p == "quality") return 4;
        try {
            return std::stoi(p);
        } catch (...) {
            return 6;
        }
    }

    static int resolve_encoder_threads(int default_threads, unsigned int hw_concurrency) {
        if (default_threads > 0) {
            return default_threads;
        }
        int threads = (hw_concurrency > 0) ? static_cast<int>(hw_concurrency) : 4;
        if (threads <= 0) threads = 4;
        if (threads > 4) threads = 4;
        return threads;
    }
};

}  // namespace pylibheif
