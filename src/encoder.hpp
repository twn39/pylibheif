#pragma once
#include "common.hpp"
#include <memory>
#include <string>
#include <vector>

namespace pylibheif {

class HeifContext;
class HeifImage;
class HeifImageHandle;

class HeifEncoderDescriptor {
public:
  HeifEncoderDescriptor(const heif_encoder_descriptor *descriptor);

  std::string id_name() const;
  std::string name() const;
  heif_compression_format compression_format() const;

  const heif_encoder_descriptor *get() const { return descriptor; }

private:
  const heif_encoder_descriptor *descriptor;
};

std::vector<HeifEncoderDescriptor> get_encoder_descriptors(
    heif_compression_format format_filter = heif_compression_undefined,
    const std::string &name_filter = "");

class HeifEncoder {
public:
  HeifEncoder(heif_compression_format format);
  HeifEncoder(const HeifEncoderDescriptor &descriptor);
  ~HeifEncoder();

  std::string name() const;

  void set_lossy_quality(int quality);
  void set_parameter(const std::string &name, const std::string &value);

  std::shared_ptr<HeifImageHandle> encode_image(HeifContext &ctx,
                                                const HeifImage &image,
                                                std::string preset = "");

  heif_encoder *get() { return encoder; }

private:
  heif_encoder *encoder;
};

} // namespace pylibheif
