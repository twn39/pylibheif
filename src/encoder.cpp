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
    heif_encoder* enc = nullptr;
    check_error(heif_context_get_encoder(nullptr, descriptor.get(), &enc));
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
    : descriptor(descriptor) {}

std::string HeifEncoderDescriptor::id_name() const {
    return heif_encoder_descriptor_get_id_name(descriptor);
}

std::string HeifEncoderDescriptor::name() const {
    return heif_encoder_descriptor_get_name(descriptor);
}

heif_compression_format HeifEncoderDescriptor::compression_format() const {
    return heif_encoder_descriptor_get_compression_format(descriptor);
}

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
