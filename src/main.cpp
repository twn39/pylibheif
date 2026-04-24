#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "context.hpp"
#include "encoder.hpp"
#include "image.hpp"

namespace nb = nanobind;
using namespace pylibheif;

NB_MODULE(_pylibheif, m) {
    m.doc() = "Python bindings for libheif using nanobind";

    // Enums
    nb::enum_<heif_error_code>(m, "HeifErrorCode")
        .value("Ok", heif_error_Ok)
        .value("InputDoesNotExist", heif_error_Input_does_not_exist)
        .value("InvalidInput", heif_error_Invalid_input)
        .value("UnsupportedFiletype", heif_error_Unsupported_filetype)
        .value("UnsupportedFeature", heif_error_Unsupported_feature)
        .value("UsageError", heif_error_Usage_error)
        .value("MemoryAllocationError", heif_error_Memory_allocation_error)
        .value("DecoderPluginError", heif_error_Decoder_plugin_error)
        .value("EncoderPluginError", heif_error_Encoder_plugin_error)
        .value("EncodingError", heif_error_Encoding_error)
        .value("ColorProfileDoesNotExist", heif_error_Color_profile_does_not_exist)
        .export_values();

    nb::enum_<heif_colorspace>(m, "HeifColorspace")
        .value("Undefined", heif_colorspace_undefined)
        .value("YCbCr", heif_colorspace_YCbCr)
        .value("RGB", heif_colorspace_RGB)
        .value("Monochrome", heif_colorspace_monochrome)
        .export_values();

    nb::enum_<heif_chroma>(m, "HeifChroma")
        .value("Undefined", heif_chroma_undefined)
        .value("Monochrome", heif_chroma_monochrome)
        .value("C420", heif_chroma_420)
        .value("C422", heif_chroma_422)
        .value("C444", heif_chroma_444)
        .value("InterleavedRGB", heif_chroma_interleaved_RGB)
        .value("InterleavedRGBA", heif_chroma_interleaved_RGBA)
        .export_values();

    nb::enum_<heif_channel>(m, "HeifChannel")
        .value("Y", heif_channel_Y)
        .value("Cb", heif_channel_Cb)
        .value("Cr", heif_channel_Cr)
        .value("R", heif_channel_R)
        .value("G", heif_channel_G)
        .value("B", heif_channel_B)
        .value("Alpha", heif_channel_Alpha)
        .value("Interleaved", heif_channel_interleaved)
        .export_values();

    nb::enum_<heif_compression_format>(m, "HeifCompressionFormat")
        .value("Undefined", heif_compression_undefined)
        .value("HEVC", heif_compression_HEVC)
        .value("AVC", heif_compression_AVC)
        .value("JPEG", heif_compression_JPEG)
        .value("AV1", heif_compression_AV1)
        .value("JPEG2000", heif_compression_JPEG2000)
        .export_values();

    // Exception
    static nb::exception<HeifError> exc(m, "HeifError");
    nb::register_exception_translator([](const std::exception_ptr& p, void* /* payload */) {
        try {
            std::rethrow_exception(p);
        } catch (const HeifError& e) {
            nb::object err = exc(e.what());
            nb::setattr(err, "code", nb::cast(static_cast<int>(e.code)));
            nb::setattr(err, "subcode", nb::cast(static_cast<int>(e.subcode)));
            PyErr_SetObject(exc.ptr(), err.ptr());
        }
    });

    // Classes
    nb::class_<HeifContext>(m, "HeifContext")
        .def(nb::init<>())
        .def("close", &HeifContext::close)
        .def("read_from_file", &HeifContext::read_from_file,
             nb::call_guard<nb::gil_scoped_release>())
        .def("read_from_memory", &HeifContext::read_from_memory)
        .def("get_primary_image_handle", &HeifContext::get_primary_image_handle,
             nb::keep_alive<0, 1>())
        .def("get_list_of_top_level_image_IDs", &HeifContext::get_list_of_top_level_image_IDs)
        .def("get_image_handle", &HeifContext::get_image_handle, nb::keep_alive<0, 1>())
        .def("write_to_file", &HeifContext::write_to_file, nb::call_guard<nb::gil_scoped_release>())
        .def("write_to_bytes", &HeifContext::write_to_bytes)
        .def("add_exif_metadata", &HeifContext::add_exif_metadata, nb::arg("handle"),
             nb::arg("data"), "Add EXIF metadata to an image. The data should be raw EXIF bytes.")
        .def("add_xmp_metadata", &HeifContext::add_xmp_metadata, nb::arg("handle"), nb::arg("data"),
             "Add XMP metadata to an image. The data should be XMP XML as bytes.")
        .def("add_generic_metadata", &HeifContext::add_generic_metadata, nb::arg("handle"),
             nb::arg("data"), nb::arg("item_type"), nb::arg("content_type") = "",
             "Add generic metadata to an image with specified item type and "
             "optional content type.")
        .def("__enter__", [](HeifContext& self) { return &self; })
        .def("__exit__", [](HeifContext& self, nb::args) { self.close(); })
        .def("__repr__", [](const HeifContext& self) {
            return "<pylibheif.HeifContext" + std::string(self.get() ? "" : " (closed)") + ">";
        });

    nb::class_<HeifImageHandle>(m, "HeifImageHandle")
        .def_prop_ro("width", &HeifImageHandle::get_width)
        .def_prop_ro("height", &HeifImageHandle::get_height)
        .def_prop_ro("has_alpha", &HeifImageHandle::has_alpha_channel)
        .def_prop_ro("luma_bits_per_pixel", &HeifImageHandle::get_luma_bits_per_pixel)
        .def_prop_ro("chroma_bits_per_pixel", &HeifImageHandle::get_chroma_bits_per_pixel)
        .def("decode", &HeifImageHandle::decode, nb::arg("colorspace") = heif_colorspace_RGB,
             nb::arg("chroma") = heif_chroma_interleaved_RGB,
             nb::call_guard<nb::gil_scoped_release>())
        .def("get_metadata_block_ids", &HeifImageHandle::get_list_of_metadata_block_IDs,
             nb::arg("type_filter") = "")
        .def("get_metadata_block_type", &HeifImageHandle::get_metadata_block_type)
        .def("get_metadata_block", &HeifImageHandle::get_metadata_block)
        .def("__repr__", [](const HeifImageHandle& self) {
            return "<pylibheif.HeifImageHandle " + std::to_string(self.get_width()) + "x" +
                   std::to_string(self.get_height()) +
                   " alpha=" + (self.has_alpha_channel() ? "True" : "False") + ">";
        });

    nb::class_<HeifImage>(m, "HeifImage")
        .def_static("from_numpy", &HeifImage::from_numpy_rgb,
                    nb::arg("arr"),
                    nb::sig("def from_numpy(arr: numpy.ndarray) -> HeifImage"))
        .def(nb::init<int, int, heif_colorspace, heif_chroma>())
        .def_prop_ro("width", nb::overload_cast<>(&HeifImage::get_width, nb::const_))
        .def_prop_ro("height", nb::overload_cast<>(&HeifImage::get_height, nb::const_))
        .def("get_width", nb::overload_cast<heif_channel>(&HeifImage::get_width, nb::const_))
        .def("get_height", nb::overload_cast<heif_channel>(&HeifImage::get_height, nb::const_))
        .def("add_plane", &HeifImage::add_plane)
        .def(
            "get_plane",
            [](std::shared_ptr<HeifImage> self, heif_channel channel, bool writeable) {
                return self->get_array(channel, writeable, nb::cast(self));
            },
            nb::arg("channel"), nb::arg("writeable") = false,
            nb::sig("def get_plane(self, channel: HeifChannel, writeable: bool = False) -> "
                    "numpy.ndarray"))
        .def("__repr__", [](const HeifImage& self) {
            return "<pylibheif.HeifImage " + std::to_string(self.get_width()) + "x" +
                   std::to_string(self.get_height()) + ">";
        });

    nb::class_<HeifEncoderDescriptor>(m, "HeifEncoderDescriptor")
        .def_prop_ro("id_name", &HeifEncoderDescriptor::id_name)
        .def_prop_ro("name", &HeifEncoderDescriptor::name)
        .def_prop_ro("compression_format", &HeifEncoderDescriptor::compression_format)
        .def("__repr__", [](const HeifEncoderDescriptor& self) {
            std::string format;
            switch (self.compression_format()) {
                case heif_compression_HEVC: format = "HEVC"; break;
                case heif_compression_AVC: format = "AVC"; break;
                case heif_compression_JPEG: format = "JPEG"; break;
                case heif_compression_AV1: format = "AV1"; break;
                case heif_compression_JPEG2000: format = "JPEG2000"; break;
                default: format = "Undefined"; break;
            }
            return "<pylibheif.HeifEncoderDescriptor id_name='" + self.id_name() + "' format=" + format + ">";
        });

    m.def("get_encoder_descriptors", &get_encoder_descriptors,
          nb::arg("format_filter") = heif_compression_undefined, nb::arg("name_filter") = "");

    nb::class_<HeifEncoder>(m, "HeifEncoder")
        .def(nb::init<heif_compression_format>(), nb::call_guard<nb::gil_scoped_release>())
        .def(nb::init<HeifEncoderDescriptor>(), nb::call_guard<nb::gil_scoped_release>())
        .def_prop_ro("name", &HeifEncoder::name)
        .def("set_lossy_quality", &HeifEncoder::set_lossy_quality)
        .def("set_lossless", &HeifEncoder::set_lossless)
        .def("set_parameter", &HeifEncoder::set_parameter)
        .def("encode_image", &HeifEncoder::encode_image, nb::arg("ctx"), nb::arg("image"),
             nb::arg("preset") = "", nb::call_guard<nb::gil_scoped_release>(),
             nb::keep_alive<0, 2>())
        .def("__repr__", [](const HeifEncoder& self) {
            return "<pylibheif.HeifEncoder name='" + self.name() + "'>";
        });
}