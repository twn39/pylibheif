#pragma once
#include <map>
#include <memory>
#include <vector>

// Removed nanobind dependency
#include <optional>
#include "common.hpp"
#include "hdr_metadata.hpp"
#include "color_profile.hpp"

namespace pylibheif {

class HeifImage;
struct ContextState;

class HeifDecodingOptions {
   public:
    HeifDecodingOptions() {
        options = heif_decoding_options_alloc();
    }
    ~HeifDecodingOptions() {
        if (options) {
            heif_decoding_options_free(options);
        }
    }

    // Rule of Five (Move-only wrapper)
    HeifDecodingOptions(const HeifDecodingOptions&) = delete;
    HeifDecodingOptions& operator=(const HeifDecodingOptions&) = delete;
    HeifDecodingOptions(HeifDecodingOptions&& other) noexcept 
        : options(other.options), m_decoder_id(std::move(other.m_decoder_id)) {
        other.options = nullptr;
    }
    HeifDecodingOptions& operator=(HeifDecodingOptions&& other) noexcept {
        if (this != &other) {
            if (options) heif_decoding_options_free(options);
            options = other.options;
            other.options = nullptr;
            m_decoder_id = std::move(other.m_decoder_id);
        }
        return *this;
    }

    heif_decoding_options* get() const { return options; }

    bool get_ignore_transformations() const { return options->ignore_transformations != 0; }
    void set_ignore_transformations(bool val) { options->ignore_transformations = val ? 1 : 0; }

    bool get_convert_hdr_to_8bit() const { return options->convert_hdr_to_8bit != 0; }
    void set_convert_hdr_to_8bit(bool val) { options->convert_hdr_to_8bit = val ? 1 : 0; }

    bool get_strict_decoding() const { return options->strict_decoding != 0; }
    void set_strict_decoding(bool val) { options->strict_decoding = val ? 1 : 0; }

    std::string get_decoder_id() const { return options->decoder_id ? options->decoder_id : ""; }
    void set_decoder_id(const std::string& val) {
        m_decoder_id = val;
        options->decoder_id = m_decoder_id.empty() ? nullptr : m_decoder_id.c_str();
    }

    int get_num_codec_threads() const { return options->num_codec_threads; }
    void set_num_codec_threads(int val) { options->num_codec_threads = val; }

    bool get_autocorrect_broken_input() const { return options->autocorrect_broken_input != 0; }
    void set_autocorrect_broken_input(bool val) { options->autocorrect_broken_input = val ? 1 : 0; }

    bool get_output_image_nclx_profile_passthrough() const { return options->output_image_nclx_profile_passthrough != 0; }
    void set_output_image_nclx_profile_passthrough(bool val) { options->output_image_nclx_profile_passthrough = val ? 1 : 0; }

   private:
    heif_decoding_options* options = nullptr;
    std::string m_decoder_id;
};

class HeifEncodingOptions {
   public:
    HeifEncodingOptions() {
        options = heif_encoding_options_alloc();
        if (!options) {
            throw std::bad_alloc();
        }
    }
    ~HeifEncodingOptions() {
        if (options) {
            heif_encoding_options_free(options);
        }
    }

    // Rule of Five (Move-only wrapper)
    HeifEncodingOptions(const HeifEncodingOptions&) = delete;
    HeifEncodingOptions& operator=(const HeifEncodingOptions&) = delete;
    HeifEncodingOptions(HeifEncodingOptions&& other) noexcept 
        : options(other.options) {
        other.options = nullptr;
    }
    HeifEncodingOptions& operator=(HeifEncodingOptions&& other) noexcept {
        if (this != &other) {
            if (options) heif_encoding_options_free(options);
            options = other.options;
            other.options = nullptr;
        }
        return *this;
    }

    heif_encoding_options* get() const { return options; }

    bool get_save_alpha_channel() const { return options->save_alpha_channel != 0; }
    void set_save_alpha_channel(bool val) { options->save_alpha_channel = val ? 1 : 0; }

    bool get_save_two_colr_boxes_when_ICC_and_nclx_available() const {
        return options->save_two_colr_boxes_when_ICC_and_nclx_available != 0;
    }
    void set_save_two_colr_boxes_when_ICC_and_nclx_available(bool val) {
        options->save_two_colr_boxes_when_ICC_and_nclx_available = val ? 1 : 0;
    }

    bool get_macOS_compatibility_workaround_no_nclx_profile() const {
        return options->macOS_compatibility_workaround_no_nclx_profile != 0;
    }
    void set_macOS_compatibility_workaround_no_nclx_profile(bool val) {
        options->macOS_compatibility_workaround_no_nclx_profile = val ? 1 : 0;
    }

    heif_orientation get_image_orientation() const { return options->image_orientation; }
    void set_image_orientation(heif_orientation val) { options->image_orientation = val; }

    bool get_prefer_uncC_short_form() const { return options->prefer_uncC_short_form != 0; }
    void set_prefer_uncC_short_form(bool val) { options->prefer_uncC_short_form = val ? 1 : 0; }

    heif_chroma_downsampling_algorithm get_preferred_chroma_downsampling_algorithm() const {
        return options->color_conversion_options.preferred_chroma_downsampling_algorithm;
    }
    void set_preferred_chroma_downsampling_algorithm(heif_chroma_downsampling_algorithm val) {
        options->color_conversion_options.preferred_chroma_downsampling_algorithm = val;
    }

    heif_chroma_upsampling_algorithm get_preferred_chroma_upsampling_algorithm() const {
        return options->color_conversion_options.preferred_chroma_upsampling_algorithm;
    }
    void set_preferred_chroma_upsampling_algorithm(heif_chroma_upsampling_algorithm val) {
        options->color_conversion_options.preferred_chroma_upsampling_algorithm = val;
    }

    bool get_only_use_preferred_chroma_algorithm() const {
        return options->color_conversion_options.only_use_preferred_chroma_algorithm != 0;
    }
    void set_only_use_preferred_chroma_algorithm(bool val) {
        options->color_conversion_options.only_use_preferred_chroma_algorithm = val ? 1 : 0;
    }

   private:
     heif_encoding_options* options = nullptr;
};

struct HeifPlaneLayout {
    heif_channel channel;
    int width;
    int height;
    int stride_bytes;
    int num_channels;
    int bits_per_pixel;
    size_t bytes_per_channel;
    bool is_big_endian;

    std::vector<size_t> shape() const {
        if (num_channels > 1) {
            return { static_cast<size_t>(height), static_cast<size_t>(width), static_cast<size_t>(num_channels) };
        }
        return { static_cast<size_t>(height), static_cast<size_t>(width) };
    }

    std::vector<int64_t> strides() const {
        int64_t elem_stride = stride_bytes / bytes_per_channel;
        if (num_channels > 1) {
            return { elem_stride, num_channels, 1 };
        }
        return { elem_stride, 1 };
    }

    std::string numpy_dtype_suffix() const {
        if (bytes_per_channel == 1) return "u1";
        const union { uint32_t i; uint8_t c[4]; } endian_test = { 0x01020304 };
        const bool host_is_little = (endian_test.c[0] == 4);
        if (host_is_little == is_big_endian) {
            return is_big_endian ? ">u2" : "<u2";
        }
        return "u2";
    }
};

class HeifImageLayout {
public:
    static HeifImageLayout from_image(const heif_image* img);
    static HeifImageLayout from_image(const HeifImage& img);

    HeifImageLayout(heif_colorspace colorspace, heif_chroma chroma, int width, int height)
        : m_colorspace(colorspace), m_chroma(chroma), m_width(width), m_height(height) {}

    HeifPlaneLayout get_plane_layout(heif_channel channel, int stride_bytes, int bits_per_pixel) const;

    heif_colorspace colorspace() const { return m_colorspace; }
    heif_chroma chroma() const { return m_chroma; }
    int width() const { return m_width; }
    int height() const { return m_height; }

private:
    heif_colorspace m_colorspace;
    heif_chroma m_chroma;
    int m_width;
    int m_height;
};

class HeifImageHandle {
   public:
    HeifImageHandle(heif_image_handle* h, std::shared_ptr<ContextState> state)
        : handle(h), m_state(state) {}

    // Rule of Five (Move-only wrapper)
    HeifImageHandle(const HeifImageHandle&) = delete;
    HeifImageHandle& operator=(const HeifImageHandle&) = delete;
    HeifImageHandle(HeifImageHandle&&) noexcept = default;
    HeifImageHandle& operator=(HeifImageHandle&&) noexcept = default;

    int get_width() const;
    int get_height() const;
    bool has_alpha_channel() const;
    int get_luma_bits_per_pixel() const;
    int get_chroma_bits_per_pixel() const;

    HeifImage decode(heif_colorspace colorspace, heif_chroma chroma, const HeifDecodingOptions* options = nullptr);

    // Auxiliary Images
    std::vector<heif_item_id> get_list_of_auxiliary_image_IDs(int aux_key_mask = 0);
    std::string get_auxiliary_type() const;
    HeifImageHandle get_auxiliary_image_handle(heif_item_id id);

    // Metadata
    std::vector<heif_item_id> get_list_of_metadata_block_IDs(const std::string& type_filter = "");
    std::string get_metadata_block_type(heif_item_id id);
    std::vector<uint8_t> get_metadata_block(heif_item_id id);

    // Color Profile
    heif_color_profile_type get_color_profile_type() const;
    std::optional<HeifColorProfileNclx> get_nclx_color_profile() const;

    // HDR Metadata
    bool has_content_light_level() const;
    bool has_mastering_display_colour_volume() const;
    bool has_ambient_viewing_environment() const;
    std::optional<HeifContentLightLevel> get_content_light_level() const;
    std::optional<HeifMasteringDisplayColourVolume> get_mastering_display_colour_volume() const;
    std::optional<HeifAmbientViewingEnvironment> get_ambient_viewing_environment() const;

    heif_image_handle* get() const { return handle.get(); }

   private:
    void check_valid() const;
    ImageHandlePtr handle;
    std::shared_ptr<ContextState> m_state;
};

class HeifImage {
   public:
    // numpy creation functions moved to bindings

    HeifImage(heif_image* img) : image(img) {}
    HeifImage(int width, int height, heif_colorspace colorspace, heif_chroma chroma);

    // Rule of Five (Move-only wrapper)
    HeifImage(const HeifImage&) = delete;
    HeifImage& operator=(const HeifImage&) = delete;
    HeifImage(HeifImage&&) noexcept = default;
    HeifImage& operator=(HeifImage&&) noexcept = default;

    int get_width() const;
    int get_height() const;
    int get_width(heif_channel channel) const;
    int get_height(heif_channel channel) const;
    void add_plane(heif_channel channel, int width, int height, int bit_depth);

    // get_array moved to bindings

    // Color Profile
    heif_color_profile_type get_color_profile_type() const;
    std::optional<HeifColorProfileNclx> get_nclx_color_profile() const;
    void set_nclx_color_profile(const HeifColorProfileNclx& color_profile);

    // HDR Metadata
    bool has_content_light_level() const;
    bool has_mastering_display_colour_volume() const;
    bool has_ambient_viewing_environment() const;
    std::optional<HeifContentLightLevel> get_content_light_level() const;
    std::optional<HeifMasteringDisplayColourVolume> get_mastering_display_colour_volume() const;
    std::optional<HeifAmbientViewingEnvironment> get_ambient_viewing_environment() const;

    void set_content_light_level(const HeifContentLightLevel& cll);
    void set_mastering_display_colour_volume(const HeifMasteringDisplayColourVolume& mdcv);
    void set_ambient_viewing_environment(const HeifAmbientViewingEnvironment& amve);

    heif_image* get() const { return image.get(); }

   private:
    ImagePtr image;
};

}  // namespace pylibheif
