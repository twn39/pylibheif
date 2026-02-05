#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "context.hpp"
#include "encoder.hpp"
#include "image.hpp"

namespace py = pybind11;
using namespace pylibheif;

class HeifPlane {
   public:
    HeifPlane(std::shared_ptr<HeifImage> img, heif_channel channel, bool writeable)
        : img(img), channel(channel), writeable(writeable) {}

    py::buffer_info get_buffer_info() { return img->get_buffer_info(channel, writeable); }

   private:
    std::shared_ptr<HeifImage> img;
    heif_channel channel;
    bool writeable;
};

PYBIND11_MODULE(pylibheif, m) {
    m.doc() = "Python bindings for libheif using pybind11";

    // Enums
    py::enum_<heif_error_code>(m, "HeifErrorCode")
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

    py::enum_<heif_colorspace>(m, "HeifColorspace")
        .value("Undefined", heif_colorspace_undefined)
        .value("YCbCr", heif_colorspace_YCbCr)
        .value("RGB", heif_colorspace_RGB)
        .value("Monochrome", heif_colorspace_monochrome)
        .export_values();

    py::enum_<heif_chroma>(m, "HeifChroma")
        .value("Undefined", heif_chroma_undefined)
        .value("Monochrome", heif_chroma_monochrome)
        .value("C420", heif_chroma_420)
        .value("C422", heif_chroma_422)
        .value("C444", heif_chroma_444)
        .value("InterleavedRGB", heif_chroma_interleaved_RGB)
        .value("InterleavedRGBA", heif_chroma_interleaved_RGBA)
        .export_values();

    py::enum_<heif_channel>(m, "HeifChannel")
        .value("Y", heif_channel_Y)
        .value("Cb", heif_channel_Cb)
        .value("Cr", heif_channel_Cr)
        .value("R", heif_channel_R)
        .value("G", heif_channel_G)
        .value("B", heif_channel_B)
        .value("Alpha", heif_channel_Alpha)
        .value("Interleaved", heif_channel_interleaved)
        .export_values();

    py::enum_<heif_compression_format>(m, "HeifCompressionFormat")
        .value("Undefined", heif_compression_undefined)
        .value("HEVC", heif_compression_HEVC)
        .value("AVC", heif_compression_AVC)
        .value("JPEG", heif_compression_JPEG)
        .value("AV1", heif_compression_AV1)
        .value("JPEG2000", heif_compression_JPEG2000)
        .export_values();

    // Exception
    py::register_exception<HeifError>(m, "HeifError");

    // Classes
    py::class_<HeifContext, std::shared_ptr<HeifContext>>(m, "HeifContext")
        .def(py::init<>())
        .def("read_from_file", &HeifContext::read_from_file)
        .def("read_from_memory", &HeifContext::read_from_memory)
        .def("get_primary_image_handle", &HeifContext::get_primary_image_handle)
        .def("get_list_of_top_level_image_IDs", &HeifContext::get_list_of_top_level_image_IDs)
        .def("get_image_handle", &HeifContext::get_image_handle)
        .def("write_to_file", &HeifContext::write_to_file)
        .def("write_to_bytes", &HeifContext::write_to_bytes)
        .def("add_exif_metadata", &HeifContext::add_exif_metadata, py::arg("handle"),
             py::arg("data"), "Add EXIF metadata to an image. The data should be raw EXIF bytes.")
        .def("add_xmp_metadata", &HeifContext::add_xmp_metadata, py::arg("handle"), py::arg("data"),
             "Add XMP metadata to an image. The data should be XMP XML as bytes.")
        .def("add_generic_metadata", &HeifContext::add_generic_metadata, py::arg("handle"),
             py::arg("data"), py::arg("item_type"), py::arg("content_type") = "",
             "Add generic metadata to an image with specified item type and "
             "optional content type.")
        .def("__enter__", [](HeifContext& self) { return &self; })
        .def("__exit__", [](HeifContext& self, py::args) {});

    py::class_<HeifImageHandle, std::shared_ptr<HeifImageHandle>>(m, "HeifImageHandle")
        .def_property_readonly("width", &HeifImageHandle::get_width)
        .def_property_readonly("height", &HeifImageHandle::get_height)
        .def_property_readonly("has_alpha", &HeifImageHandle::has_alpha_channel)
        .def("decode", &HeifImageHandle::decode, py::arg("colorspace") = heif_colorspace_RGB,
             py::arg("chroma") = heif_chroma_interleaved_RGB,
             py::call_guard<py::gil_scoped_release>())
        .def("get_metadata_block_ids", &HeifImageHandle::get_list_of_metadata_block_IDs,
             py::arg("type_filter") = "")
        .def("get_metadata_block_type", &HeifImageHandle::get_metadata_block_type)
        .def("get_metadata_block", &HeifImageHandle::get_metadata_block);

    py::class_<HeifPlane>(m, "HeifPlane", py::buffer_protocol())
        .def_buffer(&HeifPlane::get_buffer_info);

    py::class_<HeifImage, std::shared_ptr<HeifImage>>(m, "HeifImage", py::buffer_protocol())
        .def(py::init<int, int, heif_colorspace, heif_chroma>())
        .def_buffer([](HeifImage& img) -> py::buffer_info {
            return img.get_buffer_info(heif_channel_interleaved, true);
        })
        .def("get_width", &HeifImage::get_width)
        .def("get_height", &HeifImage::get_height)
        .def("add_plane", &HeifImage::add_plane)
        .def(
            "get_plane",
            [](std::shared_ptr<HeifImage> self, heif_channel channel, bool writeable) {
                return HeifPlane(self, channel, writeable);
            },
            py::arg("channel"), py::arg("writeable") = false);

    py::class_<HeifEncoderDescriptor>(m, "HeifEncoderDescriptor")
        .def_property_readonly("id_name", &HeifEncoderDescriptor::id_name)
        .def_property_readonly("name", &HeifEncoderDescriptor::name)
        .def_property_readonly("compression_format", &HeifEncoderDescriptor::compression_format);

    m.def("get_encoder_descriptors", &get_encoder_descriptors,
          py::arg("format_filter") = heif_compression_undefined, py::arg("name_filter") = "");

    py::class_<HeifEncoder, std::shared_ptr<HeifEncoder>>(m, "HeifEncoder")
        .def(py::init<heif_compression_format>())
        .def(py::init<HeifEncoderDescriptor>())
        .def_property_readonly("name", &HeifEncoder::name)
        .def("set_lossy_quality", &HeifEncoder::set_lossy_quality)
        .def("set_parameter", &HeifEncoder::set_parameter)
        .def("encode_image", &HeifEncoder::encode_image, py::arg("ctx"), py::arg("image"),
             py::arg("preset") = "", py::call_guard<py::gil_scoped_release>());
}
