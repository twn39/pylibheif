#include "encoder.hpp"
#include "context.hpp"
#include "image.hpp"

namespace pylibheif {

HeifEncoder::HeifEncoder(heif_compression_format format) {
  check_error(heif_context_get_encoder_for_format(nullptr, format, &encoder));
}

HeifEncoder::~HeifEncoder() {
  if (encoder) {
    heif_encoder_release(encoder);
  }
}

void HeifEncoder::set_lossy_quality(int quality) {
  check_error(heif_encoder_set_lossy_quality(encoder, quality));
}

void HeifEncoder::set_parameter(const std::string &name,
                                const std::string &value) {
  check_error(heif_encoder_set_parameter(encoder, name.c_str(), value.c_str()));
}

std::shared_ptr<HeifImageHandle>
HeifEncoder::encode_image(HeifContext &ctx, const HeifImage &image) {
  heif_image_handle *handle;
  check_error(heif_context_encode_image(ctx.get(), image.get(), encoder,
                                        nullptr, &handle));
  return std::make_shared<HeifImageHandle>(handle);
}

} // namespace pylibheif
