#include "encoder.hpp"

#include "context.hpp"
#include "image.hpp"

namespace pylibheif {

HeifEncoder::HeifEncoder(heif_compression_format format) {
    heif_encoder* enc = nullptr;
    check_error(heif_context_get_encoder_for_format(nullptr, format, &enc));
    encoder.reset(enc);
}

HeifEncoder::HeifEncoder(const HeifEncoderDescriptor& descriptor) {
    if (!descriptor.raw()) {
        throw std::invalid_argument("Invalid encoder descriptor.");
    }

    heif_encoder* enc = nullptr;
    check_error(heif_context_get_encoder(nullptr, descriptor.raw(), &enc));
    encoder.reset(enc);
}

std::string HeifEncoder::name() const { return heif_encoder_get_name(encoder.get()); }

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
        set_parameter("preset", preset);
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
