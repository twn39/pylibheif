#pragma once
#include <memory>
#include <string>
#include <vector>

#include "common.hpp"

namespace pylibheif {

class HeifContext;
class HeifImage;
class HeifImageHandle;

class HeifEncoderDescriptor {
   public:
    HeifEncoderDescriptor(const heif_encoder_descriptor* descriptor);

    std::string id_name() const { return m_id_name; }
    std::string name() const { return m_name; }
    heif_compression_format compression_format() const { return m_compression_format; }

   private:
    std::string m_id_name;
    std::string m_name;
    heif_compression_format m_compression_format;
};

std::vector<HeifEncoderDescriptor> get_encoder_descriptors(
    heif_compression_format format_filter = heif_compression_undefined,
    const char* name_filter = "");

class HeifEncoder {
   public:
    HeifEncoder(heif_compression_format format);
    HeifEncoder(const HeifEncoderDescriptor& descriptor);

    std::string name() const;

    void set_lossy_quality(int quality);
    void set_parameter(const char* name, const char* value);

    std::shared_ptr<HeifImageHandle> encode_image(HeifContext& ctx, const HeifImage& image,
                                                  const char* preset = "");

    heif_encoder* get() const { return encoder.get(); }

   private:
    EncoderPtr encoder;
};

}  // namespace pylibheif
