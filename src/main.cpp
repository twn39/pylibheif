#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/optional.h>
#include "hdr_metadata.hpp"

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
        .value("InterleavedRRGGBB_BE", heif_chroma_interleaved_RRGGBB_BE)
        .value("InterleavedRRGGBBAA_BE", heif_chroma_interleaved_RRGGBBAA_BE)
        .value("InterleavedRRGGBB_LE", heif_chroma_interleaved_RRGGBB_LE)
        .value("InterleavedRRGGBBAA_LE", heif_chroma_interleaved_RRGGBBAA_LE)
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
    nb::class_<HeifContentLightLevel>(m, "HeifContentLightLevel")
        .def("__init__", [](HeifContentLightLevel* self, uint16_t max_cll, uint16_t max_fall) {
            new (self) HeifContentLightLevel{max_cll, max_fall};
        }, nb::arg("max_content_light_level") = 0, nb::arg("max_pic_average_light_level") = 0)
        .def_rw("max_content_light_level", &HeifContentLightLevel::max_content_light_level)
        .def_rw("max_pic_average_light_level", &HeifContentLightLevel::max_pic_average_light_level)
        .def("__repr__", [](const HeifContentLightLevel& self) {
            return "<pylibheif.HeifContentLightLevel max_content_light_level=" +
                   std::to_string(self.max_content_light_level) +
                   " max_pic_average_light_level=" +
                   std::to_string(self.max_pic_average_light_level) + ">";
        });

    nb::class_<HeifMasteringDisplayColourVolume>(m, "HeifMasteringDisplayColourVolume")
        .def("__init__", [](HeifMasteringDisplayColourVolume* self,
                            std::pair<float, float> red,
                            std::pair<float, float> green,
                            std::pair<float, float> blue,
                            std::pair<float, float> white,
                            double max_lum, double min_lum) {
            new (self) HeifMasteringDisplayColourVolume{red, green, blue, white, max_lum, min_lum};
        }, nb::arg("red_primary") = std::make_pair(0.0f, 0.0f),
           nb::arg("green_primary") = std::make_pair(0.0f, 0.0f),
           nb::arg("blue_primary") = std::make_pair(0.0f, 0.0f),
           nb::arg("white_point") = std::make_pair(0.0f, 0.0f),
           nb::arg("max_luminance") = 0.0,
           nb::arg("min_luminance") = 0.0)
        .def_rw("red_primary", &HeifMasteringDisplayColourVolume::red_primary)
        .def_rw("green_primary", &HeifMasteringDisplayColourVolume::green_primary)
        .def_rw("blue_primary", &HeifMasteringDisplayColourVolume::blue_primary)
        .def_rw("white_point", &HeifMasteringDisplayColourVolume::white_point)
        .def_rw("max_luminance", &HeifMasteringDisplayColourVolume::max_luminance)
        .def_rw("min_luminance", &HeifMasteringDisplayColourVolume::min_luminance)
        .def("__repr__", [](const HeifMasteringDisplayColourVolume& self) {
            return "<pylibheif.HeifMasteringDisplayColourVolume"
                   " red_primary=(" + std::to_string(self.red_primary.first) + ", " + std::to_string(self.red_primary.second) + ")"
                   " green_primary=(" + std::to_string(self.green_primary.first) + ", " + std::to_string(self.green_primary.second) + ")"
                   " blue_primary=(" + std::to_string(self.blue_primary.first) + ", " + std::to_string(self.blue_primary.second) + ")"
                   " white_point=(" + std::to_string(self.white_point.first) + ", " + std::to_string(self.white_point.second) + ")"
                   " max_luminance=" + std::to_string(self.max_luminance) +
                   " min_luminance=" + std::to_string(self.min_luminance) + ">";
        });

    nb::class_<HeifAmbientViewingEnvironment>(m, "HeifAmbientViewingEnvironment")
        .def("__init__", [](HeifAmbientViewingEnvironment* self,
                            double illumination,
                            std::pair<float, float> light) {
            new (self) HeifAmbientViewingEnvironment{illumination, light};
        }, nb::arg("ambient_illumination") = 0.0,
           nb::arg("ambient_light") = std::make_pair(0.0f, 0.0f))
        .def_rw("ambient_illumination", &HeifAmbientViewingEnvironment::ambient_illumination)
        .def_rw("ambient_light", &HeifAmbientViewingEnvironment::ambient_light)
        .def("__repr__", [](const HeifAmbientViewingEnvironment& self) {
            return "<pylibheif.HeifAmbientViewingEnvironment"
                   " ambient_illumination=" + std::to_string(self.ambient_illumination) +
                   " ambient_light=(" + std::to_string(self.ambient_light.first) + ", " + std::to_string(self.ambient_light.second) + ")>";
        });

    nb::class_<HeifDecodingOptions>(m, "HeifDecodingOptions")
        .def(nb::init<>())
        .def_prop_rw("ignore_transformations", &HeifDecodingOptions::get_ignore_transformations, &HeifDecodingOptions::set_ignore_transformations)
        .def_prop_rw("convert_hdr_to_8bit", &HeifDecodingOptions::get_convert_hdr_to_8bit, &HeifDecodingOptions::set_convert_hdr_to_8bit)
        .def_prop_rw("strict_decoding", &HeifDecodingOptions::get_strict_decoding, &HeifDecodingOptions::set_strict_decoding)
        .def_prop_rw("decoder_id", &HeifDecodingOptions::get_decoder_id, &HeifDecodingOptions::set_decoder_id)
        .def_prop_rw("num_codec_threads", &HeifDecodingOptions::get_num_codec_threads, &HeifDecodingOptions::set_num_codec_threads)
        .def_prop_rw("autocorrect_broken_input", &HeifDecodingOptions::get_autocorrect_broken_input, &HeifDecodingOptions::set_autocorrect_broken_input)
        .def_prop_rw("output_image_nclx_profile_passthrough", &HeifDecodingOptions::get_output_image_nclx_profile_passthrough, &HeifDecodingOptions::set_output_image_nclx_profile_passthrough)
        .def("__repr__", [](const HeifDecodingOptions& self) {
            return "<pylibheif.HeifDecodingOptions num_codec_threads=" + std::to_string(self.get_num_codec_threads()) +
                   " strict=" + (self.get_strict_decoding() ? "True" : "False") + ">";
        });

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
             nb::arg("options") = nullptr,
             nb::call_guard<nb::gil_scoped_release>())
        .def("get_auxiliary_image_ids", &HeifImageHandle::get_list_of_auxiliary_image_IDs,
             nb::arg("aux_key_mask") = 0)
        .def("get_auxiliary_type", &HeifImageHandle::get_auxiliary_type)
        .def("get_auxiliary_image_handle", &HeifImageHandle::get_auxiliary_image_handle)
        .def("get_metadata_block_ids", &HeifImageHandle::get_list_of_metadata_block_IDs,
             nb::arg("type_filter") = "")
        .def("get_metadata_block_type", &HeifImageHandle::get_metadata_block_type)
        .def("get_metadata_block", &HeifImageHandle::get_metadata_block)
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
        .def_static("from_numpy", &HeifImage::from_numpy_rgb,
                    nb::arg("arr"),
                    nb::sig("def from_numpy(arr: numpy.ndarray) -> HeifImage"))
        .def_static("from_numpy", &HeifImage::from_numpy_rgb_16,
                    nb::arg("arr"), nb::arg("bit_depth") = 10,
                    nb::sig("def from_numpy(arr: numpy.ndarray, bit_depth: int = 10) -> HeifImage"))
        .def(nb::init<int, int, heif_colorspace, heif_chroma>())
        .def_prop_ro("width", nb::overload_cast<>(&HeifImage::get_width, nb::const_))
        .def_prop_ro("height", nb::overload_cast<>(&HeifImage::get_height, nb::const_))
        .def("get_width", nb::overload_cast<heif_channel>(&HeifImage::get_width, nb::const_))
        .def("get_height", nb::overload_cast<heif_channel>(&HeifImage::get_height, nb::const_))
        .def("add_plane", &HeifImage::add_plane)
        .def(
            "get_plane",
            [](nb::handle self, heif_channel channel, bool writeable) {
                auto& native_self = nb::cast<HeifImage&>(self);
                return native_self.get_array(channel, writeable, self);
            },
            nb::arg("channel"), nb::arg("writeable") = false,
            nb::sig("def get_plane(self, channel: HeifChannel, writeable: bool = False) -> "
                    "numpy.ndarray"))
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

    m.attr("AUX_IMAGE_FILTER_OMIT_ALPHA") = nb::cast(LIBHEIF_AUX_IMAGE_FILTER_OMIT_ALPHA);
    m.attr("AUX_IMAGE_FILTER_OMIT_DEPTH") = nb::cast(LIBHEIF_AUX_IMAGE_FILTER_OMIT_DEPTH);
}