#include "image.hpp"

#include <libheif/heif_sequences.h>

// Removed nanobind dependencies
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <thread>

#include "context.hpp"

namespace pylibheif {

static int compute_initial_default_threads() {
    const char* env_threads = std::getenv("PYLIBHEIF_NUM_THREADS");
    if (env_threads && *env_threads) {
        char* end = nullptr;
        long val = std::strtol(env_threads, &end, 10);
        if (end != env_threads && val > 0) {
            return std::clamp(static_cast<int>(val), 1, 64);
        }
    }
    unsigned int hw = std::thread::hardware_concurrency();
    int cores = (hw > 0) ? static_cast<int>(hw) : 1;
    return std::clamp(cores, 1, 4);
}

static std::atomic<int> g_default_num_codec_threads{compute_initial_default_threads()};

int get_default_num_codec_threads() {
    return g_default_num_codec_threads.load(std::memory_order_relaxed);
}

void set_default_num_codec_threads(int threads) {
    if (threads < 0) {
        throw std::invalid_argument(
            "threads must be non-negative (0 to reset to adaptive default)");
    }
    if (threads == 0) {
        g_default_num_codec_threads.store(compute_initial_default_threads(),
                                          std::memory_order_relaxed);
    } else {
        g_default_num_codec_threads.store(threads, std::memory_order_relaxed);
    }
}

int resolve_decoding_threads(int image_width, int image_height, int requested_threads) {
    if (requested_threads > 0) {
        return requested_threads;
    }
    // Resolution-aware thread sizing:
    // Small images / thumbnails have very few CTUs (<512x512).
    // Starting worker threads costs 0.5~2ms, which exceeds single-thread decode time!
    if (image_width > 0 && image_height > 0 && (image_width < 512 || image_height < 512)) {
        return 1;
    }
    return get_default_num_codec_threads();
}

HeifDecodingOptions::HeifDecodingOptions() {
    options = heif_decoding_options_alloc();
    if (options) {
        options->num_codec_threads = get_default_num_codec_threads();
    }
}

HeifDecodingOptions::HeifDecodingOptions(
    std::optional<int> num_codec_threads, std::optional<bool> ignore_transformations,
    std::optional<bool> convert_hdr_to_8bit, std::optional<bool> strict_decoding,
    const std::optional<std::string>& decoder_id, std::optional<bool> autocorrect_broken_input,
    std::optional<bool> output_image_nclx_profile_passthrough) {
    options = heif_decoding_options_alloc();
    if (options) {
        options->num_codec_threads = num_codec_threads.value_or(get_default_num_codec_threads());
        if (ignore_transformations.has_value()) {
            set_ignore_transformations(*ignore_transformations);
        }
        if (convert_hdr_to_8bit.has_value()) {
            set_convert_hdr_to_8bit(*convert_hdr_to_8bit);
        }
        if (strict_decoding.has_value()) {
            set_strict_decoding(*strict_decoding);
        }
        if (decoder_id.has_value()) {
            set_decoder_id(*decoder_id);
        }
        if (autocorrect_broken_input.has_value()) {
            set_autocorrect_broken_input(*autocorrect_broken_input);
        }
        if (output_image_nclx_profile_passthrough.has_value()) {
            set_output_image_nclx_profile_passthrough(*output_image_nclx_profile_passthrough);
        }
    }
}

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

HeifImage HeifImageHandle::decode(heif_colorspace colorspace, heif_chroma chroma,
                                  const HeifDecodingOptions* options) {
    check_valid();
    heif_image* img = nullptr;
    int w = get_width();
    int h = get_height();
    if (options) {
        int threads = options->get_num_codec_threads();
        if (threads <= 0) {
            HeifDecodingOptions effective_opts(*options);
            effective_opts.set_num_codec_threads(resolve_decoding_threads(w, h, 0));
            check_error(
                heif_decode_image(handle.get(), &img, colorspace, chroma, effective_opts.get()));
            return HeifImage(img);
        }
        check_error(heif_decode_image(handle.get(), &img, colorspace, chroma, options->get()));
        return HeifImage(img);
    }

    HeifDecodingOptions default_opts;
    default_opts.set_num_codec_threads(resolve_decoding_threads(w, h, 0));
    check_error(heif_decode_image(handle.get(), &img, colorspace, chroma, default_opts.get()));
    return HeifImage(img);
}

std::vector<heif_item_id> HeifImageHandle::get_list_of_auxiliary_image_IDs(int aux_key_mask) {
    check_valid();
    int count = heif_image_handle_get_number_of_auxiliary_images(handle.get(), aux_key_mask);
    std::vector<heif_item_id> ids(count);
    if (count > 0) {
        heif_image_handle_get_list_of_auxiliary_image_IDs(handle.get(), aux_key_mask, ids.data(),
                                                          count);
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

HeifImageTiling HeifImageHandle::get_image_tiling(bool process_transformations) const {
    check_valid();
    heif_image_tiling tiling = {};
    check_error(
        heif_image_handle_get_image_tiling(handle.get(), process_transformations ? 1 : 0, &tiling));
    HeifImageTiling res;
    res.num_columns = tiling.num_columns;
    res.num_rows = tiling.num_rows;
    res.tile_width = tiling.tile_width;
    res.tile_height = tiling.tile_height;
    res.image_width = tiling.image_width;
    res.image_height = tiling.image_height;
    res.top_offset = tiling.top_offset;
    res.left_offset = tiling.left_offset;
    return res;
}

HeifImage HeifImageHandle::decode_tile(uint32_t tile_x, uint32_t tile_y, heif_colorspace colorspace,
                                       heif_chroma chroma, const HeifDecodingOptions* options) {
    check_valid();
    heif_image* out_img = nullptr;
    HeifImageTiling tiling = get_image_tiling(true);
    int tw = (tiling.tile_width > 0) ? static_cast<int>(tiling.tile_width) : get_width();
    int th = (tiling.tile_height > 0) ? static_cast<int>(tiling.tile_height) : get_height();

    if (options) {
        int threads = options->get_num_codec_threads();
        if (threads <= 0) {
            HeifDecodingOptions effective_opts(*options);
            effective_opts.set_num_codec_threads(resolve_decoding_threads(tw, th, 0));
            check_error(heif_image_handle_decode_image_tile(
                handle.get(), &out_img, colorspace, chroma, effective_opts.get(), tile_x, tile_y));
            return HeifImage(out_img);
        }
        check_error(heif_image_handle_decode_image_tile(handle.get(), &out_img, colorspace, chroma,
                                                        options->get(), tile_x, tile_y));
        return HeifImage(out_img);
    }

    HeifDecodingOptions default_opts;
    default_opts.set_num_codec_threads(resolve_decoding_threads(tw, th, 0));
    check_error(heif_image_handle_decode_image_tile(handle.get(), &out_img, colorspace, chroma,
                                                    default_opts.get(), tile_x, tile_y));
    return HeifImage(out_img);
}

bool HeifImageHandle::has_depth_image() const {
    check_valid();
    return heif_image_handle_has_depth_image(handle.get()) != 0;
}

int HeifImageHandle::get_number_of_depth_images() const {
    check_valid();
    return heif_image_handle_get_number_of_depth_images(handle.get());
}

std::vector<heif_item_id> HeifImageHandle::get_list_of_depth_image_IDs() const {
    check_valid();
    int count = heif_image_handle_get_number_of_depth_images(handle.get());
    if (count <= 0) {
        return {};
    }
    std::vector<heif_item_id> ids(count);
    count = heif_image_handle_get_list_of_depth_image_IDs(handle.get(), ids.data(), count);
    ids.resize(count);
    return ids;
}

HeifImageHandle HeifImageHandle::get_depth_image_handle(heif_item_id depth_image_id) const {
    check_valid();
    heif_image_handle* out_depth_handle = nullptr;
    check_error(
        heif_image_handle_get_depth_image_handle(handle.get(), depth_image_id, &out_depth_handle));
    return HeifImageHandle(out_depth_handle, m_state);
}

HeifImageHandle HeifImageHandle::get_primary_depth_image_handle() const {
    auto ids = get_list_of_depth_image_IDs();
    if (ids.empty()) {
        throw std::runtime_error("Image handle does not contain any depth images");
    }
    return get_depth_image_handle(ids[0]);
}

std::optional<HeifDepthRepresentationInfo> HeifImageHandle::get_depth_representation_info(
    heif_item_id depth_image_id) const {
    check_valid();
    const heif_depth_representation_info* info = nullptr;
    int has_info =
        heif_image_handle_get_depth_image_representation_info(handle.get(), depth_image_id, &info);
    if (!has_info || !info) {
        return std::nullopt;
    }

    HeifDepthRepresentationInfo res;
    res.has_z_near = info->has_z_near != 0;
    res.has_z_far = info->has_z_far != 0;
    res.has_d_min = info->has_d_min != 0;
    res.has_d_max = info->has_d_max != 0;
    res.z_near = info->z_near;
    res.z_far = info->z_far;
    res.d_min = info->d_min;
    res.d_max = info->d_max;
    res.depth_representation_type = static_cast<int>(info->depth_representation_type);
    res.disparity_reference_view = info->disparity_reference_view;

    heif_depth_representation_info_free(info);
    return res;
}

int HeifImageHandle::get_number_of_thumbnails() const {
    check_valid();
    return heif_image_handle_get_number_of_thumbnails(handle.get());
}

std::vector<heif_item_id> HeifImageHandle::get_list_of_thumbnail_IDs() const {
    check_valid();
    int count = heif_image_handle_get_number_of_thumbnails(handle.get());
    if (count <= 0) {
        return {};
    }
    std::vector<heif_item_id> ids(count);
    count = heif_image_handle_get_list_of_thumbnail_IDs(handle.get(), ids.data(), count);
    ids.resize(count);
    return ids;
}

HeifImageHandle HeifImageHandle::get_thumbnail(heif_item_id id) const {
    check_valid();
    heif_image_handle* thumb_handle = nullptr;
    check_error(heif_image_handle_get_thumbnail(handle.get(), id, &thumb_handle));
    return HeifImageHandle(thumb_handle, m_state);
}

std::vector<heif_item_id> HeifImageHandle::get_list_of_metadata_block_IDs(
    const std::string& type_filter) {
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
        heif_image_handle* h = handle.get();
        char* dst = reinterpret_cast<char*>(result.data());
        heif_error err;
        {
            nb::gil_scoped_release release;
            err = heif_image_handle_get_metadata(h, id, dst);
        }
        check_error(err);
    }
    return result;
}

heif_color_profile_type HeifImageHandle::get_color_profile_type() const {
    check_valid();
    return heif_image_handle_get_color_profile_type(handle.get());
}

std::optional<HeifColorProfileNclx> HeifImageHandle::get_nclx_color_profile() const {
    check_valid();
    heif_color_profile_nclx* nclx = nullptr;
    heif_error err = heif_image_handle_get_nclx_color_profile(handle.get(), &nclx);
    if (err.code == heif_error_Color_profile_does_not_exist) {
        return std::nullopt;
    }
    check_error(err);
    if (!nclx) {
        return std::nullopt;
    }
    HeifColorProfileNclx result(nclx->color_primaries, nclx->transfer_characteristics,
                                nclx->matrix_coefficients, nclx->full_range_flag != 0);
    result.color_primary_red_x = nclx->color_primary_red_x;
    result.color_primary_red_y = nclx->color_primary_red_y;
    result.color_primary_green_x = nclx->color_primary_green_x;
    result.color_primary_green_y = nclx->color_primary_green_y;
    result.color_primary_blue_x = nclx->color_primary_blue_x;
    result.color_primary_blue_y = nclx->color_primary_blue_y;
    result.color_primary_white_x = nclx->color_primary_white_x;
    result.color_primary_white_y = nclx->color_primary_white_y;

    heif_nclx_color_profile_free(nclx);
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

void HeifImage::crop(int left, int right, int top, int bottom) {
    if (!image) {
        throw std::runtime_error("HeifImage is invalid");
    }
    check_error(heif_image_crop(image.get(), left, right, top, bottom));
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

std::optional<HeifMasteringDisplayColourVolume>
HeifImageHandle::get_mastering_display_colour_volume() const {
    check_valid();
    heif_mastering_display_colour_volume mdcv;
    if (heif_image_handle_get_mastering_display_colour_volume(handle.get(), &mdcv)) {
        heif_decoded_mastering_display_colour_volume decoded;
        check_error(heif_mastering_display_colour_volume_decode(&mdcv, &decoded));
        return HeifMasteringDisplayColourVolume{
            {decoded.display_primaries_x[2], decoded.display_primaries_y[2]},  // Red
            {decoded.display_primaries_x[0], decoded.display_primaries_y[0]},  // Green
            {decoded.display_primaries_x[1], decoded.display_primaries_y[1]},  // Blue
            {decoded.white_point_x, decoded.white_point_y},
            decoded.max_display_mastering_luminance,
            decoded.min_display_mastering_luminance};
    }
    return std::nullopt;
}

std::optional<HeifAmbientViewingEnvironment> HeifImageHandle::get_ambient_viewing_environment()
    const {
    check_valid();
    heif_ambient_viewing_environment amve;
    if (heif_image_handle_get_ambient_viewing_environment(handle.get(), &amve)) {
        return HeifAmbientViewingEnvironment{
            amve.ambient_illumination / 10000.0,
            {amve.ambient_light_x / 50000.0f, amve.ambient_light_y / 50000.0f}};
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

std::optional<HeifMasteringDisplayColourVolume> HeifImage::get_mastering_display_colour_volume()
    const {
    if (!has_mastering_display_colour_volume()) return std::nullopt;
    heif_mastering_display_colour_volume mdcv;
    heif_image_get_mastering_display_colour_volume(image.get(), &mdcv);
    heif_decoded_mastering_display_colour_volume decoded;
    check_error(heif_mastering_display_colour_volume_decode(&mdcv, &decoded));
    return HeifMasteringDisplayColourVolume{
        {decoded.display_primaries_x[2], decoded.display_primaries_y[2]},  // Red
        {decoded.display_primaries_x[0], decoded.display_primaries_y[0]},  // Green
        {decoded.display_primaries_x[1], decoded.display_primaries_y[1]},  // Blue
        {decoded.white_point_x, decoded.white_point_y},
        decoded.max_display_mastering_luminance,
        decoded.min_display_mastering_luminance};
}

std::optional<HeifAmbientViewingEnvironment> HeifImage::get_ambient_viewing_environment() const {
    heif_ambient_viewing_environment amve;
    if (heif_image_get_ambient_viewing_environment(image.get(), &amve)) {
        return HeifAmbientViewingEnvironment{
            amve.ambient_illumination / 10000.0,
            {amve.ambient_light_x / 50000.0f, amve.ambient_light_y / 50000.0f}};
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
    raw_mdcv.display_primaries_x[0] =
        static_cast<uint16_t>(std::round(mdcv.green_primary.first * 50000.0f));
    raw_mdcv.display_primaries_y[0] =
        static_cast<uint16_t>(std::round(mdcv.green_primary.second * 50000.0f));
    raw_mdcv.display_primaries_x[1] =
        static_cast<uint16_t>(std::round(mdcv.blue_primary.first * 50000.0f));
    raw_mdcv.display_primaries_y[1] =
        static_cast<uint16_t>(std::round(mdcv.blue_primary.second * 50000.0f));
    raw_mdcv.display_primaries_x[2] =
        static_cast<uint16_t>(std::round(mdcv.red_primary.first * 50000.0f));
    raw_mdcv.display_primaries_y[2] =
        static_cast<uint16_t>(std::round(mdcv.red_primary.second * 50000.0f));

    raw_mdcv.white_point_x = static_cast<uint16_t>(std::round(mdcv.white_point.first * 50000.0f));
    raw_mdcv.white_point_y = static_cast<uint16_t>(std::round(mdcv.white_point.second * 50000.0f));

    raw_mdcv.max_display_mastering_luminance =
        static_cast<uint32_t>(std::round(mdcv.max_luminance * 10000.0));
    raw_mdcv.min_display_mastering_luminance =
        static_cast<uint32_t>(std::round(mdcv.min_luminance * 10000.0));

    heif_image_set_mastering_display_colour_volume(image.get(), &raw_mdcv);
}

void HeifImage::set_ambient_viewing_environment(const HeifAmbientViewingEnvironment& amve) {
    heif_ambient_viewing_environment raw_amve;
    raw_amve.ambient_illumination =
        static_cast<uint32_t>(std::round(amve.ambient_illumination * 10000.0));
    raw_amve.ambient_light_x =
        static_cast<uint16_t>(std::round(amve.ambient_light.first * 50000.0f));
    raw_amve.ambient_light_y =
        static_cast<uint16_t>(std::round(amve.ambient_light.second * 50000.0f));
    heif_image_set_ambient_viewing_environment(image.get(), &raw_amve);
}

heif_color_profile_type HeifImage::get_color_profile_type() const {
    return heif_image_get_color_profile_type(image.get());
}

std::optional<HeifColorProfileNclx> HeifImage::get_nclx_color_profile() const {
    heif_color_profile_nclx* nclx = nullptr;
    heif_error err = heif_image_get_nclx_color_profile(image.get(), &nclx);
    if (err.code == heif_error_Color_profile_does_not_exist) {
        return std::nullopt;
    }
    check_error(err);
    if (!nclx) {
        return std::nullopt;
    }
    HeifColorProfileNclx result(nclx->color_primaries, nclx->transfer_characteristics,
                                nclx->matrix_coefficients, nclx->full_range_flag != 0);
    result.color_primary_red_x = nclx->color_primary_red_x;
    result.color_primary_red_y = nclx->color_primary_red_y;
    result.color_primary_green_x = nclx->color_primary_green_x;
    result.color_primary_green_y = nclx->color_primary_green_y;
    result.color_primary_blue_x = nclx->color_primary_blue_x;
    result.color_primary_blue_y = nclx->color_primary_blue_y;
    result.color_primary_white_x = nclx->color_primary_white_x;
    result.color_primary_white_y = nclx->color_primary_white_y;

    heif_nclx_color_profile_free(nclx);
    return result;
}

void HeifImage::set_nclx_color_profile(const HeifColorProfileNclx& color_profile) {
    heif_color_profile_nclx* nclx = heif_nclx_color_profile_alloc();
    if (!nclx) {
        heif_error raw_err = {heif_error_Memory_allocation_error, heif_suberror_Unspecified,
                              "Failed to allocate heif_color_profile_nclx"};
        throw HeifMemoryAllocationError(raw_err);
    }

    heif_error err = heif_nclx_color_profile_set_color_primaries(
        nclx, static_cast<uint16_t>(color_profile.color_primaries));
    if (err.code != heif_error_Ok) {
        heif_nclx_color_profile_free(nclx);
        check_error(err);
    }

    err = heif_nclx_color_profile_set_transfer_characteristics(
        nclx, static_cast<uint16_t>(color_profile.transfer_characteristics));
    if (err.code != heif_error_Ok) {
        heif_nclx_color_profile_free(nclx);
        check_error(err);
    }

    err = heif_nclx_color_profile_set_matrix_coefficients(
        nclx, static_cast<uint16_t>(color_profile.matrix_coefficients));
    if (err.code != heif_error_Ok) {
        heif_nclx_color_profile_free(nclx);
        check_error(err);
    }

    nclx->full_range_flag = color_profile.full_range_flag ? 1 : 0;

    err = heif_image_set_nclx_color_profile(image.get(), nclx);
    heif_nclx_color_profile_free(nclx);
    check_error(err);
}

HeifImageLayout HeifImageLayout::from_image(const heif_image* img) {
    heif_colorspace colorspace = heif_image_get_colorspace(img);
    heif_chroma chroma = heif_image_get_chroma_format(img);
    int width = heif_image_get_primary_width(img);
    int height = heif_image_get_primary_height(img);
    return HeifImageLayout(colorspace, chroma, width, height);
}

HeifImageLayout HeifImageLayout::from_image(const HeifImage& img) { return from_image(img.get()); }

HeifPlaneLayout HeifImageLayout::get_plane_layout(heif_channel channel, int stride_bytes,
                                                  int bits_per_pixel) const {
    HeifPlaneLayout layout;
    layout.channel = channel;
    layout.stride_bytes = stride_bytes;
    layout.bits_per_pixel = bits_per_pixel;
    layout.bytes_per_channel = (bits_per_pixel + 7) / 8;

    layout.width = m_width;
    layout.height = m_height;
    if (channel == heif_channel_Cb || channel == heif_channel_Cr) {
        if (m_chroma == heif_chroma_420) {
            layout.width = (m_width + 1) / 2;
            layout.height = (m_height + 1) / 2;
        } else if (m_chroma == heif_chroma_422) {
            layout.width = (m_width + 1) / 2;
        }
    }

    layout.num_channels = 1;
    if (channel == heif_channel_interleaved) {
        if (m_chroma == heif_chroma_interleaved_RGB ||
            m_chroma == heif_chroma_interleaved_RRGGBB_BE ||
            m_chroma == heif_chroma_interleaved_RRGGBB_LE) {
            layout.num_channels = 3;
        } else if (m_chroma == heif_chroma_interleaved_RGBA ||
                   m_chroma == heif_chroma_interleaved_RRGGBBAA_BE ||
                   m_chroma == heif_chroma_interleaved_RRGGBBAA_LE) {
            layout.num_channels = 4;
        }
    }

    layout.is_big_endian = (m_chroma == heif_chroma_interleaved_RRGGBB_BE ||
                            m_chroma == heif_chroma_interleaved_RRGGBBAA_BE);

    return layout;
}

void HeifImage::set_duration(uint32_t duration) {
    if (image) {
        heif_image_set_duration(image.get(), duration);
    }
}

uint32_t HeifImage::get_duration() const {
    if (!image) return 0;
    return heif_image_get_duration(image.get());
}

}  // namespace pylibheif

