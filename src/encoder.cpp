#include "encoder.hpp"
#include "context.hpp"
#include "image.hpp"

namespace pylibheif {

HeifEncoder::HeifEncoder(heif_compression_format format) {
  check_error(heif_context_get_encoder_for_format(nullptr, format, &encoder));
}

HeifEncoder::HeifEncoder(const HeifEncoderDescriptor &descriptor) {
  check_error(heif_context_get_encoder(nullptr, descriptor.get(), &encoder));
}

HeifEncoder::~HeifEncoder() {
  if (encoder) {
    heif_encoder_release(encoder);
  }
}

std::string HeifEncoder::name() const { return heif_encoder_get_name(encoder); }

void HeifEncoder::set_lossy_quality(int quality) {
  check_error(heif_encoder_set_lossy_quality(encoder, quality));
}

void HeifEncoder::set_parameter(const std::string &name,
                                const std::string &value) {
  check_error(heif_encoder_set_parameter(encoder, name.c_str(), value.c_str()));
}

std::shared_ptr<HeifImageHandle>
HeifEncoder::encode_image(HeifContext &ctx, const HeifImage &image,
                          std::string preset) {
  if (!preset.empty()) {
    set_parameter("preset", preset);
  }
  heif_image_handle *handle;
  check_error(heif_context_encode_image(ctx.get(), image.get(), encoder,
                                        nullptr, &handle));
  return std::make_shared<HeifImageHandle>(handle);
}

// HeifEncoderDescriptor
HeifEncoderDescriptor::HeifEncoderDescriptor(
    const heif_encoder_descriptor *descriptor)
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

std::vector<HeifEncoderDescriptor>
get_encoder_descriptors(heif_compression_format format_filter,
                        const std::string &name_filter) {
  const heif_encoder_descriptor **descriptors = nullptr;
  int count = heif_get_encoder_descriptors(
      format_filter, name_filter.empty() ? nullptr : name_filter.c_str(),
      nullptr, 0);

  std::vector<HeifEncoderDescriptor> result;
  if (count > 0) {
    descriptors = new const heif_encoder_descriptor *[count];
    heif_get_encoder_descriptors(
        format_filter, name_filter.empty() ? nullptr : name_filter.c_str(),
        descriptors, count);

    for (int i = 0; i < count; ++i) {
      result.emplace_back(descriptors[i]);
    }

    delete[] descriptors;
  }
  return result;
}

} // namespace pylibheif
