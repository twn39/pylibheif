#pragma once
#include <map>
#include <memory>
#include <vector>

#include <nanobind/ndarray.h>
#include <optional>
#include "common.hpp"
#include "hdr_metadata.hpp"

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
    nb::bytes get_metadata_block(heif_item_id id);

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
    static HeifImage from_numpy_rgb(
        nb::ndarray<uint8_t, nb::ndim<3>, nb::c_contig> arr);
    static HeifImage from_numpy_rgb_16(
        nb::ndarray<uint16_t, nb::ndim<3>, nb::c_contig> arr, int bit_depth = 10);

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

    // Array sequence support
    nb::object get_array(heif_channel channel, bool writeable = false,
                         nb::handle owner = nb::handle());

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
