#pragma once
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "common.hpp"

namespace pylibheif {

class HeifContext;
class HeifImage;
class HeifImageHandle;
class HeifEncodingOptions;

class HeifEncoderDescriptor {
   public:
    HeifEncoderDescriptor(const heif_encoder_descriptor* descriptor);

    std::string id_name() const { return m_id_name; }
    std::string name() const { return m_name; }
    heif_compression_format compression_format() const { return m_compression_format; }
    const heif_encoder_descriptor* raw() const { return m_raw_descriptor; }

   private:
    std::string m_id_name;
    std::string m_name;
    heif_compression_format m_compression_format;
    const heif_encoder_descriptor* m_raw_descriptor;
};

std::vector<HeifEncoderDescriptor> get_encoder_descriptors(
    heif_compression_format format_filter = heif_compression_undefined,
    const std::string& name_filter = "");

class HeifEncoderParameter {
   public:
    HeifEncoderParameter(const heif_encoder_parameter* param, heif_encoder* encoder);

    std::string name() const { return m_name; }
    heif_encoder_parameter_type type() const { return m_type; }
    bool has_default() const { return m_has_default; }

    std::optional<int> default_integer() const { return m_default_integer; }
    std::optional<bool> default_boolean() const { return m_default_boolean; }
    std::optional<std::string> default_string() const { return m_default_string; }

    std::optional<std::pair<int, int>> valid_integer_range() const { return m_valid_integer_range; }
    std::vector<int> valid_integer_values() const { return m_valid_integer_values; }
    std::vector<std::string> valid_string_values() const { return m_valid_string_values; }

   private:
    std::string m_name;
    heif_encoder_parameter_type m_type;
    bool m_has_default = false;
    std::optional<int> m_default_integer;
    std::optional<bool> m_default_boolean;
    std::optional<std::string> m_default_string;
    std::optional<std::pair<int, int>> m_valid_integer_range;
    std::vector<int> m_valid_integer_values;
    std::vector<std::string> m_valid_string_values;
};

class HeifEncoder {
   public:
    HeifEncoder(heif_compression_format format);
    HeifEncoder(const HeifEncoderDescriptor& descriptor);

    // Rule of Five (Move-only wrapper)
    HeifEncoder(const HeifEncoder&) = delete;
    HeifEncoder& operator=(const HeifEncoder&) = delete;
    HeifEncoder(HeifEncoder&&) noexcept = default;
    HeifEncoder& operator=(HeifEncoder&&) noexcept = default;

    std::string name() const;

    void set_lossy_quality(int quality);
    void set_lossless(bool lossless);
    void set_parameter(const std::string& name, const std::string& value);
    std::string get_parameter(const std::string& name) const;

    void set_integer_parameter(const std::string& name, int value);
    int get_integer_parameter(const std::string& name) const;

    void set_boolean_parameter(const std::string& name, bool value);
    bool get_boolean_parameter(const std::string& name) const;

    void set_string_parameter(const std::string& name, const std::string& value);
    std::string get_string_parameter(const std::string& name) const;

    std::vector<HeifEncoderParameter> list_parameters() const;

    HeifImageHandle encode_image(HeifContext& ctx, const HeifImage& image,
                                 const std::string& preset = "",
                                 const HeifEncodingOptions* options = nullptr);

    heif_encoder* get() const { return encoder.get(); }

   private:
    EncoderPtr encoder;
};

}  // namespace pylibheif
