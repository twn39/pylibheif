#include "encoder.hpp"

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cstdlib>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

#include "context.hpp"
#include "image.hpp"
#include "preset_config.hpp"

namespace pylibheif {

static std::string init_default_preset() {
    const char* env = std::getenv("PYLIBHEIF_ENCODER_PRESET");
    return (env && *env) ? std::string(env) : std::string("balanced");
}

static const std::string s_default_preset_initial = init_default_preset();
static std::atomic<const std::string*> s_default_preset_active{&s_default_preset_initial};
static std::mutex s_preset_write_mutex;
static std::vector<std::unique_ptr<std::string>> s_preset_storage;

std::string get_default_encoder_preset() {
    const std::string* ptr = s_default_preset_active.load(std::memory_order_acquire);
    return ptr ? *ptr : "balanced";
}

void set_default_encoder_preset(const std::string& preset) {
    if (preset.empty()) {
        s_default_preset_active.store(&s_default_preset_initial, std::memory_order_release);
        return;
    }
    std::lock_guard<std::mutex> lock(s_preset_write_mutex);
    s_preset_storage.push_back(std::make_unique<std::string>(preset));
    s_default_preset_active.store(s_preset_storage.back().get(), std::memory_order_release);
}

void HeifEncoder::init_parameter_cache() {
    m_supported_parameters.clear();
    if (!encoder) return;
    const heif_encoder_parameter* const* params = heif_encoder_list_parameters(encoder.get());
    if (!params) return;
    for (int i = 0; params[i]; ++i) {
        const char* p_name = heif_encoder_parameter_get_name(params[i]);
        if (p_name) {
            m_supported_parameters.emplace(p_name);
        }
    }
}

HeifEncoder::HeifEncoder(heif_compression_format format, const std::string& preset) {
    heif_encoder* enc = nullptr;
    check_error(heif_context_get_encoder_for_format(nullptr, format, &enc));
    encoder.reset(enc);
    init_parameter_cache();
    if (!preset.empty()) {
        apply_preset(preset);
    } else {
        apply_preset(get_default_encoder_preset());
    }
}

HeifEncoder::HeifEncoder(const HeifEncoderDescriptor& descriptor, const std::string& preset) {
    if (!descriptor.raw()) {
        throw std::invalid_argument("Invalid encoder descriptor.");
    }

    heif_encoder* enc = nullptr;
    check_error(heif_context_get_encoder(nullptr, descriptor.raw(), &enc));
    encoder.reset(enc);
    init_parameter_cache();
    if (!preset.empty()) {
        apply_preset(preset);
    } else {
        apply_preset(get_default_encoder_preset());
    }
}

std::string HeifEncoder::name() const { return heif_encoder_get_name(encoder.get()); }

bool HeifEncoder::has_parameter(const std::string& name) const {
    return m_supported_parameters.find(name) != m_supported_parameters.end();
}

void HeifEncoder::apply_preset(const std::string& preset) {
    if (!encoder || preset.empty()) {
        return;
    }
    std::string p = PresetMappings::normalize_preset(preset);

    // 1. Check if encoder has "preset" parameter (e.g. x265)
    if (has_parameter("preset")) {
        set_parameter("preset", PresetMappings::map_x265_preset(p));
    }

    // 2. Check if encoder has "speed" parameter (e.g. aom)
    if (has_parameter("speed")) {
        set_integer_parameter("speed", PresetMappings::map_aom_speed(p));
    }

    // 3. Multithreading & auto-tiles concurrency optimizations for encoders that support them (e.g.
    // AOM)
    if (has_parameter("threads")) {
        int threads = PresetMappings::resolve_encoder_threads(get_default_num_codec_threads(),
                                                              std::thread::hardware_concurrency());
        set_integer_parameter("threads", threads);
    }

    if (has_parameter("auto-tiles")) {
        set_boolean_parameter("auto-tiles", true);
    }
}

void HeifEncoder::set_parameters(const std::unordered_map<std::string, std::string>& params) {
    for (const auto& [k, v] : params) {
        set_parameter(k, v);
    }
}

void HeifEncoder::set_lossy_quality(int quality) {
    check_error(heif_encoder_set_lossy_quality(encoder.get(), quality));
}

void HeifEncoder::set_lossless(bool lossless) {
    check_error(heif_encoder_set_lossless(encoder.get(), lossless));
}

void HeifEncoder::set_parameter(const std::string& name, const std::string& value) {
    check_error(heif_encoder_set_parameter(encoder.get(), name.c_str(), value.c_str()));
}

std::string HeifEncoder::get_parameter(const std::string& name) const {
    char val[512];
    check_error(heif_encoder_get_parameter(encoder.get(), name.c_str(), val, sizeof(val)));
    return std::string(val);
}

void HeifEncoder::set_integer_parameter(const std::string& name, int value) {
    check_error(heif_encoder_set_parameter_integer(encoder.get(), name.c_str(), value));
}

int HeifEncoder::get_integer_parameter(const std::string& name) const {
    int value = 0;
    check_error(heif_encoder_get_parameter_integer(encoder.get(), name.c_str(), &value));
    return value;
}

void HeifEncoder::set_boolean_parameter(const std::string& name, bool value) {
    check_error(heif_encoder_set_parameter_boolean(encoder.get(), name.c_str(), value ? 1 : 0));
}

bool HeifEncoder::get_boolean_parameter(const std::string& name) const {
    int value = 0;
    check_error(heif_encoder_get_parameter_boolean(encoder.get(), name.c_str(), &value));
    return value != 0;
}

void HeifEncoder::set_string_parameter(const std::string& name, const std::string& value) {
    check_error(heif_encoder_set_parameter_string(encoder.get(), name.c_str(), value.c_str()));
}

std::string HeifEncoder::get_string_parameter(const std::string& name) const {
    char val[512];
    check_error(heif_encoder_get_parameter_string(encoder.get(), name.c_str(), val, sizeof(val)));
    return std::string(val);
}

std::vector<HeifEncoderParameter> HeifEncoder::list_parameters() const {
    std::vector<HeifEncoderParameter> result;
    const heif_encoder_parameter* const* params = heif_encoder_list_parameters(encoder.get());
    if (params) {
        for (int i = 0; params[i]; ++i) {
            result.emplace_back(params[i], encoder.get());
        }
    }
    return result;
}

// HeifEncoderParameter
HeifEncoderParameter::HeifEncoderParameter(const heif_encoder_parameter* param,
                                           heif_encoder* encoder) {
    m_name = heif_encoder_parameter_get_name(param);
    m_type = heif_encoder_parameter_get_type(param);
    m_has_default = (heif_encoder_has_default(encoder, m_name.c_str()) != 0);

    if (m_type == heif_encoder_parameter_type_integer) {
        if (m_has_default) {
            int val = 0;
            if (heif_encoder_get_parameter_integer(encoder, m_name.c_str(), &val).code ==
                heif_error_Ok) {
                m_default_integer = val;
            }
        }
        int have_min = 0, have_max = 0;
        int min_val = 0, max_val = 0;
        int num_vals = 0;
        const int* vals = nullptr;
        if (heif_encoder_parameter_integer_valid_values(
                encoder, m_name.c_str(), &have_min, &have_max, &min_val, &max_val, &num_vals, &vals)
                .code == heif_error_Ok) {
            if (have_min || have_max) {
                m_valid_integer_range = std::make_pair(min_val, max_val);
            }
            if (num_vals > 0 && vals) {
                m_valid_integer_values.assign(vals, vals + num_vals);
            }
        }
    } else if (m_type == heif_encoder_parameter_type_boolean) {
        if (m_has_default) {
            int val = 0;
            if (heif_encoder_get_parameter_boolean(encoder, m_name.c_str(), &val).code ==
                heif_error_Ok) {
                m_default_boolean = (val != 0);
            }
        }
    } else if (m_type == heif_encoder_parameter_type_string) {
        if (m_has_default) {
            char val[512];
            if (heif_encoder_get_parameter_string(encoder, m_name.c_str(), val, sizeof(val)).code ==
                heif_error_Ok) {
                m_default_string = std::string(val);
            }
        }
        const char* const* stringarray = nullptr;
        if (heif_encoder_parameter_string_valid_values(encoder, m_name.c_str(), &stringarray)
                    .code == heif_error_Ok &&
            stringarray) {
            for (int i = 0; stringarray[i]; ++i) {
                m_valid_string_values.push_back(stringarray[i]);
            }
        }
    }
}

HeifImageHandle HeifEncoder::encode_image(HeifContext& ctx, const HeifImage& image,
                                          const std::string& preset,
                                          const HeifEncodingOptions* options) {
    if (!preset.empty()) {
        apply_preset(preset);
    }
    heif_encoding_options* alloc_options = nullptr;
    const heif_encoding_options* opts_ptr = nullptr;
    if (options) {
        opts_ptr = options->get();
    } else {
        alloc_options = heif_encoding_options_alloc();
        opts_ptr = alloc_options;
    }
    heif_image_handle* handle = nullptr;
    heif_error err =
        heif_context_encode_image(ctx.get(), image.get(), encoder.get(), opts_ptr, &handle);
    if (alloc_options) {
        heif_encoding_options_free(alloc_options);
    }
    check_error(err);
    return HeifImageHandle(handle, ctx.get_state());
}

std::optional<HeifImageHandle> HeifEncoder::encode_thumbnail(
    HeifContext& ctx, const HeifImage& image, const HeifImageHandle& master_image_handle,
    int bbox_size, const HeifEncodingOptions* options) {
    heif_encoding_options* alloc_options = nullptr;
    const heif_encoding_options* opts_ptr = nullptr;
    if (options) {
        opts_ptr = options->get();
    } else {
        alloc_options = heif_encoding_options_alloc();
        opts_ptr = alloc_options;
    }
    heif_image_handle* thumb_handle = nullptr;
    heif_error err =
        heif_context_encode_thumbnail(ctx.get(), image.get(), master_image_handle.get(),
                                      encoder.get(), opts_ptr, bbox_size, &thumb_handle);
    if (alloc_options) {
        heif_encoding_options_free(alloc_options);
    }
    check_error(err);
    if (!thumb_handle) {
        return std::nullopt;
    }
    return HeifImageHandle(thumb_handle, ctx.get_state());
}

// HeifEncoderDescriptor
HeifEncoderDescriptor::HeifEncoderDescriptor(const heif_encoder_descriptor* descriptor)
    : m_id_name(heif_encoder_descriptor_get_id_name(descriptor)),
      m_name(heif_encoder_descriptor_get_name(descriptor)),
      m_compression_format(heif_encoder_descriptor_get_compression_format(descriptor)),
      m_raw_descriptor(descriptor) {}

std::vector<HeifEncoderDescriptor> get_encoder_descriptors(heif_compression_format format_filter,
                                                           const std::string& name_filter) {
    const char* nf = name_filter.empty() ? nullptr : name_filter.c_str();
    int count = heif_get_encoder_descriptors(format_filter, nf, nullptr, 0);

    std::vector<HeifEncoderDescriptor> result;
    if (count > 0) {
        std::vector<const heif_encoder_descriptor*> descriptors(count);
        heif_get_encoder_descriptors(format_filter, nf, descriptors.data(), count);

        for (int i = 0; i < count; ++i) {
            result.emplace_back(descriptors[i]);
        }
    }
    return result;
}

}  // namespace pylibheif
