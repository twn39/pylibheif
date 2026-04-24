#include "image.hpp"

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <cstring>

namespace pylibheif {

std::shared_ptr<HeifImage> HeifImage::from_numpy_rgb(
    nb::ndarray<uint8_t, nb::numpy, nb::ndim<3>, nb::c_contig> arr) {
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
    auto img = std::make_shared<HeifImage>(img_ptr);

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

int HeifImageHandle::get_width() const { return heif_image_handle_get_width(handle.get()); }

int HeifImageHandle::get_height() const { return heif_image_handle_get_height(handle.get()); }

bool HeifImageHandle::has_alpha_channel() const {
    return heif_image_handle_has_alpha_channel(handle.get());
}

int HeifImageHandle::get_luma_bits_per_pixel() const {
    return heif_image_handle_get_luma_bits_per_pixel(handle.get());
}

int HeifImageHandle::get_chroma_bits_per_pixel() const {
    return heif_image_handle_get_chroma_bits_per_pixel(handle.get());
}

std::shared_ptr<HeifImage> HeifImageHandle::decode(heif_colorspace colorspace, heif_chroma chroma) {
    heif_image* img;
    check_error(heif_decode_image(handle.get(), &img, colorspace, chroma, nullptr));
    return std::make_shared<HeifImage>(img);
}

std::vector<heif_item_id> HeifImageHandle::get_list_of_metadata_block_IDs(const char* type_filter) {
    const char* tf = (type_filter && type_filter[0] != '\0') ? type_filter : nullptr;
    int count = heif_image_handle_get_number_of_metadata_blocks(handle.get(), tf);
    std::vector<heif_item_id> ids(count);
    heif_image_handle_get_list_of_metadata_block_IDs(handle.get(), tf, ids.data(), count);
    return ids;
}

std::string HeifImageHandle::get_metadata_block_type(heif_item_id id) {
    return heif_image_handle_get_metadata_type(handle.get(), id);
}

nb::bytes HeifImageHandle::get_metadata_block(heif_item_id id) {
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

}  // namespace pylibheif
