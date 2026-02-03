#pragma once
#include "common.hpp"
#include <memory>
#include <string>

namespace pylibheif {

class HeifContext;
class HeifImage;
class HeifImageHandle;

class HeifEncoder {
public:
  HeifEncoder(heif_compression_format format);
  ~HeifEncoder();

  void set_lossy_quality(int quality);
  void set_parameter(const std::string &name, const std::string &value);

  std::shared_ptr<HeifImageHandle> encode_image(HeifContext &ctx,
                                                const HeifImage &image);

  heif_encoder *get() { return encoder; }

private:
  heif_encoder *encoder;
};

} // namespace pylibheif
