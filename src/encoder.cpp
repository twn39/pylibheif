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
    int count = heif_get_encoder_descriptors(heif_compression_undefined, nullptr, nullptr, 0);
    std::vector<const heif_encoder_descriptor*> internal_descriptors(count);
    heif_get_encoder_descriptors(heif_compression_undefined, nullptr, internal_descriptors.data(),
                                 count);

    const heif_encoder_descriptor* matched_descriptor = nullptr;
    for (const auto* desc : internal_descriptors) {
        if (std::string(heif_encoder_descriptor_get_id_name(desc)) == descriptor.id_name()) {
            matched_descriptor = desc;
            break;
        }
    }

    if (!matched_descriptor) {
        throw std::runtime_error("Encoder descriptor '" + descriptor.id_name() +
                                 "' is no longer available in libheif.");
    }

    heif_encoder* enc = nullptr;
    check_error(heif_context_get_encoder(nullptr, matched_descriptor, &enc));
    encoder.reset(enc);
}

std::string HeifEncoder::name() const { return heif_encoder_get_name(encoder.get()); }

void HeifEncoder::set_lossy_quality(int quality) {
    check_error(heif_encoder_set_lossy_quality(encoder.get(), quality));
}

void HeifEncoder::set_parameter(const char* name, const char* value) {
    check_error(heif_encoder_set_parameter(encoder.get(), name, value));
}

std::shared_ptr<HeifImageHandle> HeifEncoder::encode_image(HeifContext& ctx, const HeifImage& image,
                                                           const char* preset) {
    if (preset && preset[0] != '\0') {
        set_parameter("preset", preset);
    }
    heif_image_handle* handle = nullptr;
    check_error(heif_context_encode_image(ctx.get(), image.get(), encoder.get(), nullptr, &handle));
    return std::make_shared<HeifImageHandle>(handle);
}

// HeifEncoderDescriptor
HeifEncoderDescriptor::HeifEncoderDescriptor(const heif_encoder_descriptor* descriptor)
    : m_id_name(heif_encoder_descriptor_get_id_name(descriptor)),
      m_name(heif_encoder_descriptor_get_name(descriptor)),
      m_compression_format(heif_encoder_descriptor_get_compression_format(descriptor)) {}

std::vector<HeifEncoderDescriptor> get_encoder_descriptors(heif_compression_format format_filter,
                                                           const char* name_filter) {
    const char* nf = (name_filter && name_filter[0] != '\0') ? name_filter : nullptr;
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
