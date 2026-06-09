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
    heif_error err = heif_context_encode_image(ctx.get(), image.get(), encoder.get(), opts_ptr, &handle);
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
