#include "image.hpp"

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <cstring>
#include <cmath>
#include "context.hpp"

namespace pylibheif {

HeifImage HeifImage::from_numpy_rgb(
    nb::ndarray<uint8_t, nb::ndim<3>, nb::c_contig> arr) {
    if (arr.ndim() != 3) {
        throw std::invalid_argument("Array must be 3-dimensional (H, W, C)");
    }
    int height = static_cast<int>(arr.shape(0));
    int width = static_cast<int>(arr.shape(1));
    int channels = static_cast<int>(arr.shape(2));

    if (channels != 3 && channels != 4) {
        throw std::invalid_argument("Array must have 3 (RGB) or 4 (RGBA) channels");
    }

    heif_chroma chroma =
        (channels == 4) ? heif_chroma_interleaved_RGBA : heif_chroma_interleaved_RGB;

    heif_image* img_ptr = nullptr;
    check_error(heif_image_create(width, height, heif_colorspace_RGB, chroma, &img_ptr));
    HeifImage img(img_ptr);

    check_error(heif_image_add_plane(img_ptr, heif_channel_interleaved, width, height, 8));

    int stride = 0;
    uint8_t* dst = heif_image_get_plane(img_ptr, heif_channel_interleaved, &stride);
    if (!dst) {
        throw std::runtime_error("Failed to get writable image plane");
    }

    const uint8_t* src = arr.data();
    const size_t row_bytes = static_cast<size_t>(width) * channels;

    {
        nb::gil_scoped_release release;
        if (stride == static_cast<int>(row_bytes)) {
            // Contiguous copy
            std::memcpy(dst, src, static_cast<size_t>(height) * row_bytes);
        } else {
            // Copy row by row
            for (int y = 0; y < height; ++y) {
                std::memcpy(dst + y * stride, src + y * row_bytes, row_bytes);
            }
        }
    }

    return img;
}

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

HeifImage HeifImageHandle::decode(heif_colorspace colorspace, heif_chroma chroma) {
    check_valid();
    heif_image* img;
    check_error(heif_decode_image(handle.get(), &img, colorspace, chroma, nullptr));
    return HeifImage(img);
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

nb::bytes HeifImageHandle::get_metadata_block(heif_item_id id) {
    check_valid();
    size_t size = heif_image_handle_get_metadata_size(handle.get(), id);
    PyObject* py_bytes = PyBytes_FromStringAndSize(nullptr, static_cast<Py_ssize_t>(size));
    if (!py_bytes) {
        throw std::bad_alloc();
    }
    nb::object bytes_obj = nb::steal(py_bytes);
    char* buffer = PyBytes_AS_STRING(bytes_obj.ptr());
    check_error(heif_image_handle_get_metadata(handle.get(), id, buffer));
    return nb::cast<nb::bytes>(bytes_obj);
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

nb::object HeifImage::get_array(heif_channel channel, bool writeable, nb::handle owner) {
    int stride;
    uint8_t* data;
    if (writeable) {
        data = heif_image_get_plane(image.get(), channel, &stride);
    } else {
        data = const_cast<uint8_t*>(heif_image_get_plane_readonly(image.get(), channel, &stride));
    }

    if (!data) {
        throw std::runtime_error("Failed to get image plane data");
    }

    int width = heif_image_get_width(image.get(), channel);
    int height = heif_image_get_height(image.get(), channel);
    int bpp_per_channel = heif_image_get_bits_per_pixel_range(image.get(), channel);

    // Determine number of channels for interleaved formats
    int num_channels = 1;
    heif_chroma chroma = heif_image_get_chroma_format(image.get());
    if (chroma == heif_chroma_interleaved_RGB) {
        num_channels = 3;
    } else if (chroma == heif_chroma_interleaved_RGBA ||
               chroma == heif_chroma_interleaved_RRGGBB_BE ||
               chroma == heif_chroma_interleaved_RRGGBB_LE ||
               chroma == heif_chroma_interleaved_RRGGBBAA_BE ||
               chroma == heif_chroma_interleaved_RRGGBBAA_LE) {
        num_channels = 4;
    }

    size_t bytes_per_channel = (bpp_per_channel + 7) / 8;
    int64_t elem_stride = stride / bytes_per_channel;

    size_t shape[3] = {(size_t)height, (size_t)width, (size_t)num_channels};
    int64_t strides[3] = {elem_stride, num_channels, 1};

    if (num_channels > 1) {
        // Interleaved format: return 3D array (height, width, channels)
        if (bytes_per_channel == 1) {
            return nb::cast(nb::ndarray<uint8_t, nb::numpy>(data, 3, shape, owner, strides));
        } else {
            return nb::cast(nb::ndarray<uint16_t, nb::numpy>(data, 3, shape, owner, strides));
        }
    } else {
        // Single channel: return 2D array (height, width)
        if (bytes_per_channel == 1) {
            return nb::cast(nb::ndarray<uint8_t, nb::numpy>(data, 2, shape, owner, strides));
        } else {
            return nb::cast(nb::ndarray<uint16_t, nb::numpy>(data, 2, shape, owner, strides));
        }
    }
}

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
