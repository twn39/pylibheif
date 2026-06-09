#include "image.hpp"

// Removed nanobind dependencies
#include <cstring>
#include <cmath>
#include "context.hpp"

namespace pylibheif {

// from_numpy_rgb and from_numpy_rgb_16 moved to bindings_image.cpp

void HeifImageHandle::check_valid() const {
    if (!m_state || m_state->is_closed) {
        throw std::runtime_error("HeifContext has been closed");
    }
}

int HeifImageHandle::get_width() const {
    check_valid();
    return heif_image_handle_get_width(handle.get());
}

int HeifImageHandle::get_height() const {
    check_valid();
    return heif_image_handle_get_height(handle.get());
}

bool HeifImageHandle::has_alpha_channel() const {
    check_valid();
    return heif_image_handle_has_alpha_channel(handle.get());
}

int HeifImageHandle::get_luma_bits_per_pixel() const {
    check_valid();
    return heif_image_handle_get_luma_bits_per_pixel(handle.get());
}

int HeifImageHandle::get_chroma_bits_per_pixel() const {
    check_valid();
    return heif_image_handle_get_chroma_bits_per_pixel(handle.get());
}

HeifImage HeifImageHandle::decode(heif_colorspace colorspace, heif_chroma chroma, const HeifDecodingOptions* options) {
    check_valid();
    heif_image* img;
    const heif_decoding_options* raw_opts = options ? options->get() : nullptr;
    check_error(heif_decode_image(handle.get(), &img, colorspace, chroma, raw_opts));
    return HeifImage(img);
}

std::vector<heif_item_id> HeifImageHandle::get_list_of_auxiliary_image_IDs(int aux_key_mask) {
    check_valid();
    int count = heif_image_handle_get_number_of_auxiliary_images(handle.get(), aux_key_mask);
    std::vector<heif_item_id> ids(count);
    if (count > 0) {
        heif_image_handle_get_list_of_auxiliary_image_IDs(handle.get(), aux_key_mask, ids.data(), count);
    }
    return ids;
}

std::string HeifImageHandle::get_auxiliary_type() const {
    check_valid();
    const char* type_str = nullptr;
    check_error(heif_image_handle_get_auxiliary_type(handle.get(), &type_str));
    std::string result(type_str ? type_str : "");
    heif_image_handle_release_auxiliary_type(handle.get(), &type_str);
    return result;
}

HeifImageHandle HeifImageHandle::get_auxiliary_image_handle(heif_item_id id) {
    check_valid();
    heif_image_handle* aux_handle = nullptr;
    check_error(heif_image_handle_get_auxiliary_image_handle(handle.get(), id, &aux_handle));
    return HeifImageHandle(aux_handle, m_state);
}

std::vector<heif_item_id> HeifImageHandle::get_list_of_metadata_block_IDs(const std::string& type_filter) {
    check_valid();
    const char* tf = type_filter.empty() ? nullptr : type_filter.c_str();
    int count = heif_image_handle_get_number_of_metadata_blocks(handle.get(), tf);
    std::vector<heif_item_id> ids(count);
    heif_image_handle_get_list_of_metadata_block_IDs(handle.get(), tf, ids.data(), count);
    return ids;
}

std::string HeifImageHandle::get_metadata_block_type(heif_item_id id) {
    check_valid();
    return heif_image_handle_get_metadata_type(handle.get(), id);
}

std::vector<uint8_t> HeifImageHandle::get_metadata_block(heif_item_id id) {
    check_valid();
    size_t size = heif_image_handle_get_metadata_size(handle.get(), id);
    std::vector<uint8_t> result(size);
    if (size > 0) {
        check_error(heif_image_handle_get_metadata(handle.get(), id, reinterpret_cast<char*>(result.data())));
    }
    return result;
}

HeifImage::HeifImage(int width, int height, heif_colorspace colorspace, heif_chroma chroma) {
    heif_image* img = nullptr;
    check_error(heif_image_create(width, height, colorspace, chroma, &img));
    image.reset(img);
}

int HeifImage::get_width() const { return heif_image_get_primary_width(image.get()); }
int HeifImage::get_height() const { return heif_image_get_primary_height(image.get()); }

int HeifImage::get_width(heif_channel channel) const {
    return heif_image_get_width(image.get(), channel);
}

int HeifImage::get_height(heif_channel channel) const {
    return heif_image_get_height(image.get(), channel);
}

void HeifImage::add_plane(heif_channel channel, int width, int height, int bit_depth) {
    check_error(heif_image_add_plane(image.get(), channel, width, height, bit_depth));
}

// get_array moved to bindings_image.cpp

bool HeifImageHandle::has_content_light_level() const {
    check_valid();
    return heif_image_handle_has_content_light_level(handle.get()) != 0;
}

bool HeifImageHandle::has_mastering_display_colour_volume() const {
    check_valid();
    return heif_image_handle_has_mastering_display_colour_volume(handle.get()) != 0;
}

bool HeifImageHandle::has_ambient_viewing_environment() const {
    check_valid();
    return heif_image_handle_has_ambient_viewing_environment(handle.get()) != 0;
}

std::optional<HeifContentLightLevel> HeifImageHandle::get_content_light_level() const {
    check_valid();
    heif_content_light_level cll;
    if (heif_image_handle_get_content_light_level(handle.get(), &cll)) {
        return HeifContentLightLevel{cll.max_content_light_level, cll.max_pic_average_light_level};
    }
    return std::nullopt;
}

std::optional<HeifMasteringDisplayColourVolume> HeifImageHandle::get_mastering_display_colour_volume() const {
    check_valid();
    heif_mastering_display_colour_volume mdcv;
    if (heif_image_handle_get_mastering_display_colour_volume(handle.get(), &mdcv)) {
        heif_decoded_mastering_display_colour_volume decoded;
        check_error(heif_mastering_display_colour_volume_decode(&mdcv, &decoded));
        return HeifMasteringDisplayColourVolume{
            {decoded.display_primaries_x[2], decoded.display_primaries_y[2]}, // Red
            {decoded.display_primaries_x[0], decoded.display_primaries_y[0]}, // Green
            {decoded.display_primaries_x[1], decoded.display_primaries_y[1]}, // Blue
            {decoded.white_point_x, decoded.white_point_y},
            decoded.max_display_mastering_luminance,
            decoded.min_display_mastering_luminance
        };
    }
    return std::nullopt;
}

std::optional<HeifAmbientViewingEnvironment> HeifImageHandle::get_ambient_viewing_environment() const {
    check_valid();
    heif_ambient_viewing_environment amve;
    if (heif_image_handle_get_ambient_viewing_environment(handle.get(), &amve)) {
        return HeifAmbientViewingEnvironment{
            amve.ambient_illumination / 10000.0,
            {amve.ambient_light_x / 50000.0f, amve.ambient_light_y / 50000.0f}
        };
    }
    return std::nullopt;
}

bool HeifImage::has_content_light_level() const {
    return heif_image_has_content_light_level(image.get()) != 0;
}

bool HeifImage::has_mastering_display_colour_volume() const {
    return heif_image_has_mastering_display_colour_volume(image.get()) != 0;
}

bool HeifImage::has_ambient_viewing_environment() const {
    return heif_image_has_ambient_viewing_environment(image.get()) != 0;
}

std::optional<HeifContentLightLevel> HeifImage::get_content_light_level() const {
    if (!has_content_light_level()) return std::nullopt;
    heif_content_light_level cll;
    heif_image_get_content_light_level(image.get(), &cll);
    return HeifContentLightLevel{cll.max_content_light_level, cll.max_pic_average_light_level};
}

std::optional<HeifMasteringDisplayColourVolume> HeifImage::get_mastering_display_colour_volume() const {
    if (!has_mastering_display_colour_volume()) return std::nullopt;
    heif_mastering_display_colour_volume mdcv;
    heif_image_get_mastering_display_colour_volume(image.get(), &mdcv);
    heif_decoded_mastering_display_colour_volume decoded;
    check_error(heif_mastering_display_colour_volume_decode(&mdcv, &decoded));
    return HeifMasteringDisplayColourVolume{
        {decoded.display_primaries_x[2], decoded.display_primaries_y[2]}, // Red
        {decoded.display_primaries_x[0], decoded.display_primaries_y[0]}, // Green
        {decoded.display_primaries_x[1], decoded.display_primaries_y[1]}, // Blue
        {decoded.white_point_x, decoded.white_point_y},
        decoded.max_display_mastering_luminance,
        decoded.min_display_mastering_luminance
    };
}

std::optional<HeifAmbientViewingEnvironment> HeifImage::get_ambient_viewing_environment() const {
    heif_ambient_viewing_environment amve;
    if (heif_image_get_ambient_viewing_environment(image.get(), &amve)) {
        return HeifAmbientViewingEnvironment{
            amve.ambient_illumination / 10000.0,
            {amve.ambient_light_x / 50000.0f, amve.ambient_light_y / 50000.0f}
        };
    }
    return std::nullopt;
}

void HeifImage::set_content_light_level(const HeifContentLightLevel& cll) {
    heif_content_light_level raw_cll;
    raw_cll.max_content_light_level = cll.max_content_light_level;
    raw_cll.max_pic_average_light_level = cll.max_pic_average_light_level;
    heif_image_set_content_light_level(image.get(), &raw_cll);
}

void HeifImage::set_mastering_display_colour_volume(const HeifMasteringDisplayColourVolume& mdcv) {
    heif_mastering_display_colour_volume raw_mdcv;
    raw_mdcv.display_primaries_x[0] = static_cast<uint16_t>(std::round(mdcv.green_primary.first * 50000.0f));
    raw_mdcv.display_primaries_y[0] = static_cast<uint16_t>(std::round(mdcv.green_primary.second * 50000.0f));
    raw_mdcv.display_primaries_x[1] = static_cast<uint16_t>(std::round(mdcv.blue_primary.first * 50000.0f));
    raw_mdcv.display_primaries_y[1] = static_cast<uint16_t>(std::round(mdcv.blue_primary.second * 50000.0f));
    raw_mdcv.display_primaries_x[2] = static_cast<uint16_t>(std::round(mdcv.red_primary.first * 50000.0f));
    raw_mdcv.display_primaries_y[2] = static_cast<uint16_t>(std::round(mdcv.red_primary.second * 50000.0f));
    
    raw_mdcv.white_point_x = static_cast<uint16_t>(std::round(mdcv.white_point.first * 50000.0f));
    raw_mdcv.white_point_y = static_cast<uint16_t>(std::round(mdcv.white_point.second * 50000.0f));
    
    raw_mdcv.max_display_mastering_luminance = static_cast<uint32_t>(std::round(mdcv.max_luminance * 10000.0));
    raw_mdcv.min_display_mastering_luminance = static_cast<uint32_t>(std::round(mdcv.min_luminance * 10000.0));
    
    heif_image_set_mastering_display_colour_volume(image.get(), &raw_mdcv);
}

void HeifImage::set_ambient_viewing_environment(const HeifAmbientViewingEnvironment& amve) {
    heif_ambient_viewing_environment raw_amve;
    raw_amve.ambient_illumination = static_cast<uint32_t>(std::round(amve.ambient_illumination * 10000.0));
    raw_amve.ambient_light_x = static_cast<uint16_t>(std::round(amve.ambient_light.first * 50000.0f));
    raw_amve.ambient_light_y = static_cast<uint16_t>(std::round(amve.ambient_light.second * 50000.0f));
    heif_image_set_ambient_viewing_environment(image.get(), &raw_amve);
}

}  // namespace pylibheif
