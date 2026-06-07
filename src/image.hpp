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

    HeifImage decode(heif_colorspace colorspace, heif_chroma chroma);

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
