#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/optional.h>
#include <cstring>
#include <cmath>
#include "image.hpp"
#include "context.hpp"

namespace nb = nanobind;

namespace pylibheif {

HeifImage from_numpy_rgb_impl(nb::ndarray<uint8_t, nb::ndim<3>, nb::c_contig> arr) {
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

HeifImage from_numpy_rgb_16_impl(nb::ndarray<uint16_t, nb::ndim<3>, nb::c_contig> arr, int bit_depth) {
    if (arr.ndim() != 3) {
        throw std::invalid_argument("Array must be 3-dimensional (H, W, C)");
    }
    int height = static_cast<int>(arr.shape(0));
    int width = static_cast<int>(arr.shape(1));
    int channels = static_cast<int>(arr.shape(2));

    if (channels != 3 && channels != 4) {
        throw std::invalid_argument("Array must have 3 (RGB) or 4 (RGBA) channels");
    }

    if (bit_depth < 9 || bit_depth > 16) {
        throw std::invalid_argument("Bit depth must be between 9 and 16");
    }

    heif_chroma chroma =
        (channels == 4) ? heif_chroma_interleaved_RRGGBBAA_LE : heif_chroma_interleaved_RRGGBB_LE;

    heif_image* img_ptr = nullptr;
    check_error(heif_image_create(width, height, heif_colorspace_RGB, chroma, &img_ptr));
    HeifImage img(img_ptr);

    check_error(heif_image_add_plane(img_ptr, heif_channel_interleaved, width, height, bit_depth));

    int stride = 0;
    uint8_t* dst_bytes = heif_image_get_plane(img_ptr, heif_channel_interleaved, &stride);
    if (!dst_bytes) {
        throw std::runtime_error("Failed to get writable image plane");
    }

    uint16_t* dst = reinterpret_cast<uint16_t*>(dst_bytes);
    int stride_elements = stride / sizeof(uint16_t);

    const uint16_t* src = arr.data();
    const size_t row_elements = static_cast<size_t>(width) * channels;

    {
        nb::gil_scoped_release release;
        if (stride_elements == static_cast<int>(row_elements)) {
            // Contiguous copy
            std::memcpy(dst, src, static_cast<size_t>(height) * row_elements * sizeof(uint16_t));
        } else {
            // Copy row by row
            for (int y = 0; y < height; ++y) {
                std::memcpy(dst + y * stride_elements, src + y * row_elements, row_elements * sizeof(uint16_t));
            }
        }
    }

    return img;
}

nb::object get_image_plane_array(nb::handle self, heif_channel channel, bool writeable) {
    auto& native_self = nb::cast<HeifImage&>(self);
    int stride;
    uint8_t* data;
    if (writeable) {
        data = heif_image_get_plane(native_self.get(), channel, &stride);
    } else {
        data = const_cast<uint8_t*>(heif_image_get_plane_readonly(native_self.get(), channel, &stride));
    }

    if (!data) {
        throw std::runtime_error("Failed to get image plane data");
    }

    int width = heif_image_get_width(native_self.get(), channel);
    int height = heif_image_get_height(native_self.get(), channel);
    int bpp_per_channel = heif_image_get_bits_per_pixel_range(native_self.get(), channel);

    // Determine number of channels for interleaved formats
    int num_channels = 1;
    heif_chroma chroma = heif_image_get_chroma_format(native_self.get());
    if (chroma == heif_chroma_interleaved_RGB ||
        chroma == heif_chroma_interleaved_RRGGBB_BE ||
        chroma == heif_chroma_interleaved_RRGGBB_LE) {
        num_channels = 3;
    } else if (chroma == heif_chroma_interleaved_RGBA ||
               chroma == heif_chroma_interleaved_RRGGBBAA_BE ||
               chroma == heif_chroma_interleaved_RRGGBBAA_LE) {
        num_channels = 4;
    }

    size_t bytes_per_channel = (bpp_per_channel + 7) / 8;
    int64_t elem_stride = stride / bytes_per_channel;

    size_t shape[3] = {(size_t)height, (size_t)width, (size_t)num_channels};
    int64_t strides[3] = {elem_stride, num_channels, 1};

    nb::object arr_obj;
    if (num_channels > 1) {
        // Interleaved format: return 3D array (height, width, channels)
        if (bytes_per_channel == 1) {
            arr_obj = nb::cast(nb::ndarray<uint8_t, nb::numpy>(data, 3, shape, self, strides));
        } else {
            arr_obj = nb::cast(nb::ndarray<uint16_t, nb::numpy>(data, 3, shape, self, strides));
        }
    } else {
        // Single channel: return 2D array (height, width)
        if (bytes_per_channel == 1) {
            arr_obj = nb::cast(nb::ndarray<uint8_t, nb::numpy>(data, 2, shape, self, strides));
        } else {
            arr_obj = nb::cast(nb::ndarray<uint16_t, nb::numpy>(data, 2, shape, self, strides));
        }
    }

    if (bytes_per_channel > 1) {
        bool is_be_format = (chroma == heif_chroma_interleaved_RRGGBB_BE ||
                             chroma == heif_chroma_interleaved_RRGGBBAA_BE);
        bool is_le_format = (chroma == heif_chroma_interleaved_RRGGBB_LE ||
                             chroma == heif_chroma_interleaved_RRGGBBAA_LE);

        const union {
            uint32_t i;
            uint8_t c[4];
        } endian_test = {0x01020304};
        const bool is_little_endian = (endian_test.c[0] == 4);

        if (is_little_endian) {
            if (is_be_format) {
                arr_obj = arr_obj.attr("view")(">u2");
            }
        } else {
            if (is_le_format) {
                arr_obj = arr_obj.attr("view")("<u2");
            }
        }
    }

    return arr_obj;
}

void bind_image(nb::module_& m) {
    nb::class_<HeifImageHandle>(m, "HeifImageHandle")
        .def_prop_ro("width", &HeifImageHandle::get_width)
        .def_prop_ro("height", &HeifImageHandle::get_height)
        .def_prop_ro("has_alpha", &HeifImageHandle::has_alpha_channel)
        .def_prop_ro("luma_bits_per_pixel", &HeifImageHandle::get_luma_bits_per_pixel)
        .def_prop_ro("chroma_bits_per_pixel", &HeifImageHandle::get_chroma_bits_per_pixel)
        .def("decode", &HeifImageHandle::decode, nb::arg("colorspace") = heif_colorspace_RGB,
             nb::arg("chroma") = heif_chroma_interleaved_RGB,
             nb::arg("options") = nullptr,
             nb::call_guard<nb::gil_scoped_release>())
        .def("get_auxiliary_image_ids", &HeifImageHandle::get_list_of_auxiliary_image_IDs,
             nb::arg("aux_key_mask") = 0)
        .def("get_auxiliary_type", &HeifImageHandle::get_auxiliary_type)
        .def("get_auxiliary_image_handle", &HeifImageHandle::get_auxiliary_image_handle)
        .def("get_metadata_block_ids", &HeifImageHandle::get_list_of_metadata_block_IDs,
             nb::arg("type_filter") = "")
        .def("get_metadata_block_type", &HeifImageHandle::get_metadata_block_type)
        .def("get_metadata_block", [](HeifImageHandle& self, heif_item_id id) {
            std::vector<uint8_t> block = self.get_metadata_block(id);
            return nb::bytes(reinterpret_cast<const char*>(block.data()), block.size());
        })
        .def_prop_ro("has_content_light_level", &HeifImageHandle::has_content_light_level)
        .def_prop_ro("has_mastering_display_colour_volume", &HeifImageHandle::has_mastering_display_colour_volume)
        .def_prop_ro("has_ambient_viewing_environment", &HeifImageHandle::has_ambient_viewing_environment)
        .def_prop_ro("content_light_level", &HeifImageHandle::get_content_light_level)
        .def_prop_ro("mastering_display_colour_volume", &HeifImageHandle::get_mastering_display_colour_volume)
        .def_prop_ro("ambient_viewing_environment", &HeifImageHandle::get_ambient_viewing_environment)
        .def("__repr__", [](const HeifImageHandle& self) {
            return "<pylibheif.HeifImageHandle " + std::to_string(self.get_width()) + "x" +
                   std::to_string(self.get_height()) +
                   " alpha=" + (self.has_alpha_channel() ? "True" : "False") + ">";
        });

    nb::class_<HeifImage>(m, "HeifImage")
        .def_static("from_numpy", &from_numpy_rgb_impl,
                    nb::arg("arr"),
                    nb::sig("def from_numpy(arr: numpy.ndarray) -> HeifImage"))
        .def_static("from_numpy", &from_numpy_rgb_16_impl,
                    nb::arg("arr"), nb::arg("bit_depth") = 10,
                    nb::sig("def from_numpy(arr: numpy.ndarray, bit_depth: int = 10) -> HeifImage"))
        .def(nb::init<int, int, heif_colorspace, heif_chroma>())
        .def_prop_ro("width", nb::overload_cast<>(&HeifImage::get_width, nb::const_))
        .def_prop_ro("height", nb::overload_cast<>(&HeifImage::get_height, nb::const_))
        .def("get_width", nb::overload_cast<heif_channel>(&HeifImage::get_width, nb::const_))
        .def("get_height", nb::overload_cast<heif_channel>(&HeifImage::get_height, nb::const_))
        .def("add_plane", &HeifImage::add_plane)
        .def("get_plane", &get_image_plane_array,
            nb::arg("channel"), nb::arg("writeable") = false,
            nb::sig("def get_plane(self, channel: HeifChannel, writeable: bool = False) -> numpy.ndarray"))
        .def_prop_ro("has_content_light_level", &HeifImage::has_content_light_level)
        .def_prop_ro("has_mastering_display_colour_volume", &HeifImage::has_mastering_display_colour_volume)
        .def_prop_ro("has_ambient_viewing_environment", &HeifImage::has_ambient_viewing_environment)
        .def_prop_rw("content_light_level",
            [](const HeifImage& self) { return self.get_content_light_level(); },
            [](HeifImage& self, const HeifContentLightLevel& val) { self.set_content_light_level(val); })
        .def_prop_rw("mastering_display_colour_volume",
            [](const HeifImage& self) { return self.get_mastering_display_colour_volume(); },
            [](HeifImage& self, const HeifMasteringDisplayColourVolume& val) { self.set_mastering_display_colour_volume(val); })
        .def_prop_rw("ambient_viewing_environment",
            [](const HeifImage& self) { return self.get_ambient_viewing_environment(); },
            [](HeifImage& self, const HeifAmbientViewingEnvironment& val) { self.set_ambient_viewing_environment(val); })
        .def("__repr__", [](const HeifImage& self) {
            return "<pylibheif.HeifImage " + std::to_string(self.get_width()) + "x" +
                   std::to_string(self.get_height()) + ">";
        });
}

} // namespace pylibheif
