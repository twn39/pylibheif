#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/vector.h>

#include "context.hpp"
#include "encoder.hpp"
#include "hdr_metadata.hpp"
#include "image.hpp"
#include "track.hpp"

namespace nb = nanobind;
using namespace pylibheif;

namespace pylibheif {
void bind_image(nb::module_& m);
}

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

    nb::enum_<heif_color_profile_type>(m, "HeifColorProfileType")
        .value("NotPresent", heif_color_profile_type_not_present)
        .value("Nclx", heif_color_profile_type_nclx)
        .value("RICC", heif_color_profile_type_rICC)
        .value("Prof", heif_color_profile_type_prof)
        .export_values();

    nb::enum_<heif_color_primaries>(m, "HeifColorPrimaries")
        .value("ITU_R_BT_709_5", heif_color_primaries_ITU_R_BT_709_5)
        .value("Unspecified", heif_color_primaries_unspecified)
        .value("ITU_R_BT_470_6_System_M", heif_color_primaries_ITU_R_BT_470_6_System_M)
        .value("ITU_R_BT_470_6_System_B_G", heif_color_primaries_ITU_R_BT_470_6_System_B_G)
        .value("ITU_R_BT_601_6", heif_color_primaries_ITU_R_BT_601_6)
        .value("SMPTE_240M", heif_color_primaries_SMPTE_240M)
        .value("GenericFilm", heif_color_primaries_generic_film)
        .value("ITU_R_BT_2020_2_and_2100_0", heif_color_primaries_ITU_R_BT_2020_2_and_2100_0)
        .value("SMPTE_ST_428_1", heif_color_primaries_SMPTE_ST_428_1)
        .value("SMPTE_RP_431_2", heif_color_primaries_SMPTE_RP_431_2)
        .value("SMPTE_EG_432_1", heif_color_primaries_SMPTE_EG_432_1)
        .value("EBU_Tech_3213_E", heif_color_primaries_EBU_Tech_3213_E)
        .export_values();

    nb::enum_<heif_transfer_characteristics>(m, "HeifTransferCharacteristics")
        .value("ITU_R_BT_709_5", heif_transfer_characteristic_ITU_R_BT_709_5)
        .value("Unspecified", heif_transfer_characteristic_unspecified)
        .value("ITU_R_BT_470_6_System_M", heif_transfer_characteristic_ITU_R_BT_470_6_System_M)
        .value("ITU_R_BT_470_6_System_B_G", heif_transfer_characteristic_ITU_R_BT_470_6_System_B_G)
        .value("ITU_R_BT_601_6", heif_transfer_characteristic_ITU_R_BT_601_6)
        .value("SMPTE_240M", heif_transfer_characteristic_SMPTE_240M)
        .value("Linear", heif_transfer_characteristic_linear)
        .value("Logarithmic_100", heif_transfer_characteristic_logarithmic_100)
        .value("Logarithmic_100_sqrt10", heif_transfer_characteristic_logarithmic_100_sqrt10)
        .value("IEC_61966_2_4", heif_transfer_characteristic_IEC_61966_2_4)
        .value("ITU_R_BT_1361", heif_transfer_characteristic_ITU_R_BT_1361)
        .value("IEC_61966_2_1", heif_transfer_characteristic_IEC_61966_2_1)
        .value("ITU_R_BT_2020_2_10bit", heif_transfer_characteristic_ITU_R_BT_2020_2_10bit)
        .value("ITU_R_BT_2020_2_12bit", heif_transfer_characteristic_ITU_R_BT_2020_2_12bit)
        .value("ITU_R_BT_2100_0_PQ", heif_transfer_characteristic_ITU_R_BT_2100_0_PQ)
        .value("SMPTE_ST_428_1", heif_transfer_characteristic_SMPTE_ST_428_1)
        .value("ITU_R_BT_2100_0_HLG", heif_transfer_characteristic_ITU_R_BT_2100_0_HLG)
        .export_values();

    nb::enum_<heif_matrix_coefficients>(m, "HeifMatrixCoefficients")
        .value("RGB_GBR", heif_matrix_coefficients_RGB_GBR)
        .value("ITU_R_BT_709_5", heif_matrix_coefficients_ITU_R_BT_709_5)
        .value("Unspecified", heif_matrix_coefficients_unspecified)
        .value("US_FCC_T47", heif_matrix_coefficients_US_FCC_T47)
        .value("ITU_R_BT_470_6_System_B_G", heif_matrix_coefficients_ITU_R_BT_470_6_System_B_G)
        .value("ITU_R_BT_601_6", heif_matrix_coefficients_ITU_R_BT_601_6)
        .value("SMPTE_240M", heif_matrix_coefficients_SMPTE_240M)
        .value("YCgCo", heif_matrix_coefficients_YCgCo)
        .value("ITU_R_BT_2020_2_non_constant_luminance",
               heif_matrix_coefficients_ITU_R_BT_2020_2_non_constant_luminance)
        .value("ITU_R_BT_2020_2_constant_luminance",
               heif_matrix_coefficients_ITU_R_BT_2020_2_constant_luminance)
        .value("SMPTE_ST_2085", heif_matrix_coefficients_SMPTE_ST_2085)
        .value("Chromaticity_derived_non_constant_luminance",
               heif_matrix_coefficients_chromaticity_derived_non_constant_luminance)
        .value("Chromaticity_derived_constant_luminance",
               heif_matrix_coefficients_chromaticity_derived_constant_luminance)
        .value("ICtCp", heif_matrix_coefficients_ICtCp)
        .export_values();

    // Exception registrations
    static nb::exception<HeifError> exc(m, "HeifError");
    static nb::exception<HeifInputDoesNotExistError> input_not_found_exc(
        m, "HeifInputDoesNotExistError", exc.ptr());
    static nb::exception<HeifInvalidInputError> invalid_input_exc(m, "HeifInvalidInputError",
                                                                  exc.ptr());
    static nb::exception<HeifUnsupportedFiletypeError> unsupported_filetype_exc(
        m, "HeifUnsupportedFiletypeError", exc.ptr());
    static nb::exception<HeifUnsupportedFeatureError> unsupported_feature_exc(
        m, "HeifUnsupportedFeatureError", exc.ptr());
    static nb::exception<HeifUsageError> usage_exc(m, "HeifUsageError", exc.ptr());
    static nb::exception<HeifMemoryAllocationError> memory_exc(m, "HeifMemoryAllocationError",
                                                               exc.ptr());
    static nb::exception<HeifEncodingError> encoding_exc(m, "HeifEncodingError", exc.ptr());
    static nb::exception<HeifColorProfileDoesNotExistError> color_profile_exc(
        m, "HeifColorProfileDoesNotExistError", exc.ptr());

    nb::register_exception_translator([](const std::exception_ptr& p, void* /* payload */) {
        auto set_attrs = [](nb::object& err, const HeifError& e) {
            nb::setattr(err, "code", nb::cast(static_cast<int>(e.code)));
            nb::setattr(err, "subcode", nb::cast(static_cast<int>(e.subcode)));
            nb::setattr(err, "code_name", nb::cast(get_error_code_name(e.code)));
            nb::setattr(err, "code_enum", nb::cast(e.code));
        };
        try {
            std::rethrow_exception(p);
        } catch (const HeifInputDoesNotExistError& e) {
            nb::object err = input_not_found_exc(e.what());
            set_attrs(err, e);
            PyErr_SetObject(input_not_found_exc.ptr(), err.ptr());
        } catch (const HeifInvalidInputError& e) {
            nb::object err = invalid_input_exc(e.what());
            set_attrs(err, e);
            PyErr_SetObject(invalid_input_exc.ptr(), err.ptr());
        } catch (const HeifUnsupportedFiletypeError& e) {
            nb::object err = unsupported_filetype_exc(e.what());
            set_attrs(err, e);
            PyErr_SetObject(unsupported_filetype_exc.ptr(), err.ptr());
        } catch (const HeifUnsupportedFeatureError& e) {
            nb::object err = unsupported_feature_exc(e.what());
            set_attrs(err, e);
            PyErr_SetObject(unsupported_feature_exc.ptr(), err.ptr());
        } catch (const HeifUsageError& e) {
            nb::object err = usage_exc(e.what());
            set_attrs(err, e);
            PyErr_SetObject(usage_exc.ptr(), err.ptr());
        } catch (const HeifMemoryAllocationError& e) {
            nb::object err = memory_exc(e.what());
            set_attrs(err, e);
            PyErr_SetObject(memory_exc.ptr(), err.ptr());
        } catch (const HeifEncodingError& e) {
            nb::object err = encoding_exc(e.what());
            set_attrs(err, e);
            PyErr_SetObject(encoding_exc.ptr(), err.ptr());
        } catch (const HeifColorProfileDoesNotExistError& e) {
            nb::object err = color_profile_exc(e.what());
            set_attrs(err, e);
            PyErr_SetObject(color_profile_exc.ptr(), err.ptr());
        } catch (const HeifError& e) {
            nb::object err = exc(e.what());
            set_attrs(err, e);
            PyErr_SetObject(exc.ptr(), err.ptr());
        }
    });

    // Classes
    nb::class_<HeifContentLightLevel>(m, "HeifContentLightLevel")
        .def(
            "__init__",
            [](HeifContentLightLevel* self, uint16_t max_cll, uint16_t max_fall) {
                new (self) HeifContentLightLevel{max_cll, max_fall};
            },
            nb::arg("max_content_light_level") = 0, nb::arg("max_pic_average_light_level") = 0)
        .def_rw("max_content_light_level", &HeifContentLightLevel::max_content_light_level)
        .def_rw("max_pic_average_light_level", &HeifContentLightLevel::max_pic_average_light_level)
        .def("__repr__", [](const HeifContentLightLevel& self) {
            return "<pylibheif.HeifContentLightLevel max_content_light_level=" +
                   std::to_string(self.max_content_light_level) + " max_pic_average_light_level=" +
                   std::to_string(self.max_pic_average_light_level) + ">";
        });

    nb::class_<HeifMasteringDisplayColourVolume>(m, "HeifMasteringDisplayColourVolume")
        .def(
            "__init__",
            [](HeifMasteringDisplayColourVolume* self, std::pair<float, float> red,
               std::pair<float, float> green, std::pair<float, float> blue,
               std::pair<float, float> white, double max_lum, double min_lum) {
                new (self)
                    HeifMasteringDisplayColourVolume{red, green, blue, white, max_lum, min_lum};
            },
            nb::arg("red_primary") = std::make_pair(0.0f, 0.0f),
            nb::arg("green_primary") = std::make_pair(0.0f, 0.0f),
            nb::arg("blue_primary") = std::make_pair(0.0f, 0.0f),
            nb::arg("white_point") = std::make_pair(0.0f, 0.0f), nb::arg("max_luminance") = 0.0,
            nb::arg("min_luminance") = 0.0)
        .def_rw("red_primary", &HeifMasteringDisplayColourVolume::red_primary)
        .def_rw("green_primary", &HeifMasteringDisplayColourVolume::green_primary)
        .def_rw("blue_primary", &HeifMasteringDisplayColourVolume::blue_primary)
        .def_rw("white_point", &HeifMasteringDisplayColourVolume::white_point)
        .def_rw("max_luminance", &HeifMasteringDisplayColourVolume::max_luminance)
        .def_rw("min_luminance", &HeifMasteringDisplayColourVolume::min_luminance)
        .def("__repr__", [](const HeifMasteringDisplayColourVolume& self) {
            return "<pylibheif.HeifMasteringDisplayColourVolume"
                   " red_primary=(" +
                   std::to_string(self.red_primary.first) + ", " +
                   std::to_string(self.red_primary.second) +
                   ")"
                   " green_primary=(" +
                   std::to_string(self.green_primary.first) + ", " +
                   std::to_string(self.green_primary.second) +
                   ")"
                   " blue_primary=(" +
                   std::to_string(self.blue_primary.first) + ", " +
                   std::to_string(self.blue_primary.second) +
                   ")"
                   " white_point=(" +
                   std::to_string(self.white_point.first) + ", " +
                   std::to_string(self.white_point.second) +
                   ")"
                   " max_luminance=" +
                   std::to_string(self.max_luminance) +
                   " min_luminance=" + std::to_string(self.min_luminance) + ">";
        });

    nb::class_<HeifAmbientViewingEnvironment>(m, "HeifAmbientViewingEnvironment")
        .def(
            "__init__",
            [](HeifAmbientViewingEnvironment* self, double illumination,
               std::pair<float, float> light) {
                new (self) HeifAmbientViewingEnvironment{illumination, light};
            },
            nb::arg("ambient_illumination") = 0.0,
            nb::arg("ambient_light") = std::make_pair(0.0f, 0.0f))
        .def_rw("ambient_illumination", &HeifAmbientViewingEnvironment::ambient_illumination)
        .def_rw("ambient_light", &HeifAmbientViewingEnvironment::ambient_light)
        .def("__repr__", [](const HeifAmbientViewingEnvironment& self) {
            return "<pylibheif.HeifAmbientViewingEnvironment"
                   " ambient_illumination=" +
                   std::to_string(self.ambient_illumination) + " ambient_light=(" +
                   std::to_string(self.ambient_light.first) + ", " +
                   std::to_string(self.ambient_light.second) + ")>";
        });

    nb::class_<HeifDecodingOptions>(m, "HeifDecodingOptions")
        .def(nb::init<std::optional<int>, std::optional<bool>, std::optional<bool>,
                      std::optional<bool>, const std::optional<std::string>&, std::optional<bool>,
                      std::optional<bool>>(),
             nb::arg("num_codec_threads") = nb::none(),
             nb::arg("ignore_transformations") = nb::none(),
             nb::arg("convert_hdr_to_8bit") = nb::none(), nb::arg("strict_decoding") = nb::none(),
             nb::arg("decoder_id") = nb::none(), nb::arg("autocorrect_broken_input") = nb::none(),
             nb::arg("output_image_nclx_profile_passthrough") = nb::none())
        .def_prop_rw("ignore_transformations", &HeifDecodingOptions::get_ignore_transformations,
                     &HeifDecodingOptions::set_ignore_transformations)
        .def_prop_rw("convert_hdr_to_8bit", &HeifDecodingOptions::get_convert_hdr_to_8bit,
                     &HeifDecodingOptions::set_convert_hdr_to_8bit)
        .def_prop_rw("strict_decoding", &HeifDecodingOptions::get_strict_decoding,
                     &HeifDecodingOptions::set_strict_decoding)
        .def_prop_rw("decoder_id", &HeifDecodingOptions::get_decoder_id,
                     &HeifDecodingOptions::set_decoder_id)
        .def_prop_rw("num_codec_threads", &HeifDecodingOptions::get_num_codec_threads,
                     &HeifDecodingOptions::set_num_codec_threads)
        .def_prop_rw("autocorrect_broken_input", &HeifDecodingOptions::get_autocorrect_broken_input,
                     &HeifDecodingOptions::set_autocorrect_broken_input)
        .def_prop_rw("output_image_nclx_profile_passthrough",
                     &HeifDecodingOptions::get_output_image_nclx_profile_passthrough,
                     &HeifDecodingOptions::set_output_image_nclx_profile_passthrough)
        .def_prop_rw("ignore_sequence_editlist", &HeifDecodingOptions::get_ignore_sequence_editlist,
                     &HeifDecodingOptions::set_ignore_sequence_editlist)
        .def("__repr__", [](const HeifDecodingOptions& self) {
            return "<pylibheif.HeifDecodingOptions num_codec_threads=" +
                   std::to_string(self.get_num_codec_threads()) +
                   " strict=" + (self.get_strict_decoding() ? "True" : "False") + ">";
        });

    nb::enum_<heif_orientation>(m, "HeifOrientation")
        .value("Normal", heif_orientation_normal)
        .value("FlipHorizontally", heif_orientation_flip_horizontally)
        .value("Rotate180", heif_orientation_rotate_180)
        .value("FlipVertically", heif_orientation_flip_vertically)
        .value("Rotate90CwThenFlipHorizontally",
               heif_orientation_rotate_90_cw_then_flip_horizontally)
        .value("Rotate90Cw", heif_orientation_rotate_90_cw)
        .value("Rotate90CwThenFlipVertically", heif_orientation_rotate_90_cw_then_flip_vertically)
        .value("Rotate270Cw", heif_orientation_rotate_270_cw)
        .export_values();

    nb::enum_<heif_chroma_downsampling_algorithm>(m, "HeifChromaDownsamplingAlgorithm")
        .value("NearestNeighbor", heif_chroma_downsampling_nearest_neighbor)
        .value("Average", heif_chroma_downsampling_average)
        .value("SharpYuv", heif_chroma_downsampling_sharp_yuv)
        .export_values();

    nb::enum_<heif_chroma_upsampling_algorithm>(m, "HeifChromaUpsamplingAlgorithm")
        .value("NearestNeighbor", heif_chroma_upsampling_nearest_neighbor)
        .value("Bilinear", heif_chroma_upsampling_bilinear)
        .export_values();

    nb::class_<HeifEncodingOptions>(m, "HeifEncodingOptions")
        .def(nb::init<>())
        .def_prop_rw("save_alpha_channel", &HeifEncodingOptions::get_save_alpha_channel,
                     &HeifEncodingOptions::set_save_alpha_channel)
        .def_prop_rw("save_two_colr_boxes_when_ICC_and_nclx_available",
                     &HeifEncodingOptions::get_save_two_colr_boxes_when_ICC_and_nclx_available,
                     &HeifEncodingOptions::set_save_two_colr_boxes_when_ICC_and_nclx_available)
        .def_prop_rw("macOS_compatibility_workaround_no_nclx_profile",
                     &HeifEncodingOptions::get_macOS_compatibility_workaround_no_nclx_profile,
                     &HeifEncodingOptions::set_macOS_compatibility_workaround_no_nclx_profile)
        .def_prop_rw("image_orientation", &HeifEncodingOptions::get_image_orientation,
                     &HeifEncodingOptions::set_image_orientation)
        .def_prop_rw("prefer_uncC_short_form", &HeifEncodingOptions::get_prefer_uncC_short_form,
                     &HeifEncodingOptions::set_prefer_uncC_short_form)
        .def_prop_rw("preferred_chroma_downsampling_algorithm",
                     &HeifEncodingOptions::get_preferred_chroma_downsampling_algorithm,
                     &HeifEncodingOptions::set_preferred_chroma_downsampling_algorithm)
        .def_prop_rw("preferred_chroma_upsampling_algorithm",
                     &HeifEncodingOptions::get_preferred_chroma_upsampling_algorithm,
                     &HeifEncodingOptions::set_preferred_chroma_upsampling_algorithm)
        .def_prop_rw("only_use_preferred_chroma_algorithm",
                     &HeifEncodingOptions::get_only_use_preferred_chroma_algorithm,
                     &HeifEncodingOptions::set_only_use_preferred_chroma_algorithm)
        .def("__repr__", [](const HeifEncodingOptions& self) {
            return "<pylibheif.HeifEncodingOptions save_alpha_channel=" +
                   (self.get_save_alpha_channel() ? std::string("True") : std::string("False")) +
                   " prefer_uncC_short_form=" +
                   (self.get_prefer_uncC_short_form() ? std::string("True")
                                                      : std::string("False")) +
                   ">";
        });

    nb::class_<HeifContext>(m, "HeifContext")
        .def(nb::init<>())
        .def("close", &HeifContext::close)
        .def("reset", &HeifContext::reset)
        .def_prop_ro("is_closed", &HeifContext::is_closed)
        .def("read_from_file", &HeifContext::read_from_file,
             nb::call_guard<nb::gil_scoped_release>())
        .def("read_from_memory", &HeifContext::read_from_memory)
        .def("read_from_stream", &HeifContext::read_from_stream, nb::arg("stream"),
             "Read HEIF data from a Python file-like stream object implementing read(), seek(), "
             "tell().")
        .def("get_primary_image_handle", &HeifContext::get_primary_image_handle,
             nb::keep_alive<0, 1>())
        .def("get_list_of_top_level_image_IDs", &HeifContext::get_list_of_top_level_image_IDs)
        .def("get_image_handle", &HeifContext::get_image_handle, nb::keep_alive<0, 1>())
        .def("write_to_file", &HeifContext::write_to_file, nb::call_guard<nb::gil_scoped_release>())
        .def("write_to_bytes", &HeifContext::write_to_bytes, nb::arg("copy") = true,
             "Export context to Python bytes (copy=True) or zero-copy memoryview (copy=False).")
        .def("write_to_memoryview", &HeifContext::write_to_memoryview,
             "Export context directly to a zero-copy Python memoryview.")
        .def("write_to_stream", &HeifContext::write_to_stream, nb::arg("stream"),
             "Write HEIF data directly to a Python file-like stream object implementing write().")
        .def("add_exif_metadata", &HeifContext::add_exif_metadata, nb::arg("handle"),
             nb::arg("data"), "Add EXIF metadata to an image. The data should be raw EXIF bytes.")
        .def("add_xmp_metadata", &HeifContext::add_xmp_metadata, nb::arg("handle"), nb::arg("data"),
             "Add XMP metadata to an image. The data should be XMP XML as bytes.")
        .def("add_generic_metadata", &HeifContext::add_generic_metadata, nb::arg("handle"),
             nb::arg("data"), nb::arg("item_type"), nb::arg("content_type") = "",
             "Add generic metadata to an image with specified item type and "
             "optional content type.")
        .def("assign_thumbnail", &HeifContext::assign_thumbnail, nb::arg("master_image"),
             nb::arg("thumbnail_image"), "Assign a thumbnail image to a master image.")
        .def("assign_auxiliary_image", &HeifContext::assign_auxiliary_image,
             nb::arg("master_image"), nb::arg("auxiliary_image"), nb::arg("auxiliary_type"),
             "Assign an auxiliary image (such as an HDR gain map) to a master image.")
        .def("set_primary_image", &HeifContext::set_primary_image, nb::arg("handle"),
             "Designate an image handle as the primary image of the context.")
        .def("set_major_brand", &HeifContext::set_major_brand, nb::arg("brand"),
             "Set the major brand of the HEIF container (4-character FourCC).")
        .def("add_compatible_brand", &HeifContext::add_compatible_brand, nb::arg("brand"),
             "Add a compatible brand to the HEIF container (4-character FourCC).")
        .def("has_sequence", &HeifContext::has_sequence,
             "Check whether the HEIF file contains an image sequence track.")
        .def("get_sequence_timescale", &HeifContext::get_sequence_timescale,
             "Get the sequence timescale (clock ticks per second).")
        .def("get_sequence_duration", &HeifContext::get_sequence_duration,
             "Get total sequence duration in timescale ticks.")
        .def("get_number_of_sequence_tracks", &HeifContext::get_number_of_sequence_tracks,
             "Get number of sequence tracks in the HEIF file.")
        .def("get_sequence_track_ids", &HeifContext::get_sequence_track_ids,
             "Get list of sequence track IDs.")
        .def("get_track", &HeifContext::get_track, nb::arg("track_id") = 0,
             "Get a HeifTrack object for track_id (0 for first visual track).")
        .def(
            "add_visual_sequence_track",
            [](HeifContext& self, uint16_t width, uint16_t height, nb::handle track_type,
               uint32_t timescale) {
                uint32_t tt = static_cast<uint32_t>(heif_track_type_image_sequence);
                if (!track_type.is_none()) {
                    if (nb::isinstance<nb::int_>(track_type)) {
                        tt = nb::cast<uint32_t>(track_type);
                    } else if (nb::hasattr(track_type, "value")) {
                        tt = nb::cast<uint32_t>(track_type.attr("value"));
                    }
                }
                return self.add_visual_sequence_track(width, height, tt, timescale);
            },
            nb::arg("width"), nb::arg("height"), nb::arg("track_type") = nb::none(),
            nb::arg("timescale") = 1000, "Add a new visual sequence track to the HEIF container.")
        .def("set_sequence_timescale", &HeifContext::set_sequence_timescale, nb::arg("timescale"),
             "Set global sequence timescale.")
        .def("set_number_of_sequence_repetitions", &HeifContext::set_number_of_sequence_repetitions,
             nb::arg("repetitions"), "Set playback repetition count (0 = infinite loop).")
        .def("set_max_decoding_threads", &HeifContext::set_max_decoding_threads,
             nb::arg("max_threads"),
             "Set maximum background threads for parallel tile decoding (0 to decode in main "
             "thread).")
        .def("get_max_decoding_threads", &HeifContext::get_max_decoding_threads,
             "Get maximum background threads used for parallel tile decoding.")
        .def_prop_rw("max_decoding_threads", &HeifContext::get_max_decoding_threads,
                     &HeifContext::set_max_decoding_threads,
                     "Maximum background threads for parallel tile decoding.")
        .def("__enter__", [](HeifContext& self) { return &self; })
        .def("__exit__", [](HeifContext& self, nb::args) { self.close(); })
        .def("__repr__", [](const HeifContext& self) {
            return "<pylibheif.HeifContext" + std::string(self.get() ? "" : " (closed)") + ">";
        });

    nb::enum_<heif_track_type_4cc>(m, "HeifTrackType")
        .value("Video", heif_track_type_video)
        .value("ImageSequence", heif_track_type_image_sequence)
        .value("Auxiliary", heif_track_type_auxiliary)
        .value("Metadata", heif_track_type_metadata);

    nb::class_<HeifTrack>(m, "HeifTrack")
        .def_prop_ro("id", &HeifTrack::id)
        .def_prop_ro("track_type", &HeifTrack::track_type)
        .def_prop_ro("timescale", &HeifTrack::timescale)
        .def_prop_ro("number_of_repetitions", &HeifTrack::number_of_repetitions)
        .def_prop_ro("resolution", &HeifTrack::resolution)
        .def_prop_ro("has_alpha_channel", &HeifTrack::has_alpha_channel)
        .def("encode_sequence_image", &HeifTrack::encode_sequence_image, nb::arg("image"),
             nb::arg("encoder"), nb::arg("save_alpha") = false,
             "Encode a single image frame into the sequence track.")
        .def("encode_end_of_sequence", &HeifTrack::encode_end_of_sequence, nb::arg("encoder"),
             "Signal the end of frame sequence to the encoder.")
        .def("decode_next_image", &HeifTrack::decode_next_image,
             nb::arg("colorspace") = heif_colorspace_RGB, nb::arg("chroma") = heif_chroma_undefined,
             nb::arg("options") = nullptr,
             "Decode the next image frame from the track. Returns None at end of sequence.")
        .def("rewind", &HeifTrack::rewind,
             "Rewind sequence track playback back to the first frame.")
        .def("__repr__", [](const HeifTrack& self) {
            auto res = self.resolution();
            return "<pylibheif.HeifTrack id=" + std::to_string(self.id()) + " " +
                   std::to_string(res.first) + "x" + std::to_string(res.second) + ">";
        });

    bind_image(m);

    nb::class_<HeifEncoderDescriptor>(m, "HeifEncoderDescriptor")
        .def_prop_ro("id_name", &HeifEncoderDescriptor::id_name)
        .def_prop_ro("name", &HeifEncoderDescriptor::name)
        .def_prop_ro("compression_format", &HeifEncoderDescriptor::compression_format)
        .def("__repr__", [](const HeifEncoderDescriptor& self) {
            std::string format;
            switch (self.compression_format()) {
                case heif_compression_HEVC:
                    format = "HEVC";
                    break;
                case heif_compression_AVC:
                    format = "AVC";
                    break;
                case heif_compression_JPEG:
                    format = "JPEG";
                    break;
                case heif_compression_AV1:
                    format = "AV1";
                    break;
                case heif_compression_JPEG2000:
                    format = "JPEG2000";
                    break;
                default:
                    format = "Undefined";
                    break;
            }
            return "<pylibheif.HeifEncoderDescriptor id_name='" + self.id_name() +
                   "' format=" + format + ">";
        });

    m.def("get_encoder_descriptors", &get_encoder_descriptors,
          nb::arg("format_filter") = heif_compression_undefined, nb::arg("name_filter") = "");

    nb::enum_<heif_encoder_parameter_type>(m, "HeifEncoderParameterType")
        .value("Integer", heif_encoder_parameter_type_integer)
        .value("Boolean", heif_encoder_parameter_type_boolean)
        .value("String", heif_encoder_parameter_type_string)
        .export_values();

    nb::class_<HeifEncoderParameter>(m, "HeifEncoderParameter")
        .def_prop_ro("name", &HeifEncoderParameter::name)
        .def_prop_ro("type", &HeifEncoderParameter::type)
        .def_prop_ro("has_default", &HeifEncoderParameter::has_default)
        .def_prop_ro("default_value",
                     [](const HeifEncoderParameter& self) -> nb::object {
                         if (!self.has_default()) return nb::none();
                         if (self.type() == heif_encoder_parameter_type_integer) {
                             auto val = self.default_integer();
                             return val ? nb::cast(*val) : nb::none();
                         } else if (self.type() == heif_encoder_parameter_type_boolean) {
                             auto val = self.default_boolean();
                             return val ? nb::cast(*val) : nb::none();
                         } else if (self.type() == heif_encoder_parameter_type_string) {
                             auto val = self.default_string();
                             return val ? nb::cast(*val) : nb::none();
                         }
                         return nb::none();
                     })
        .def_prop_ro("valid_integer_range",
                     [](const HeifEncoderParameter& self) -> nb::object {
                         auto range = self.valid_integer_range();
                         if (range) {
                             return nb::make_tuple(range->first, range->second);
                         }
                         return nb::none();
                     })
        .def_prop_ro("valid_integer_values",
                     [](const HeifEncoderParameter& self) -> nb::object {
                         auto vals = self.valid_integer_values();
                         if (!vals.empty()) {
                             return nb::cast(vals);
                         }
                         return nb::none();
                     })
        .def_prop_ro("valid_string_values",
                     [](const HeifEncoderParameter& self) -> nb::object {
                         auto vals = self.valid_string_values();
                         if (!vals.empty()) {
                             return nb::cast(vals);
                         }
                         return nb::none();
                     })
        .def("__repr__", [](const HeifEncoderParameter& self) {
            std::string type_str;
            switch (self.type()) {
                case heif_encoder_parameter_type_integer:
                    type_str = "Integer";
                    break;
                case heif_encoder_parameter_type_boolean:
                    type_str = "Boolean";
                    break;
                case heif_encoder_parameter_type_string:
                    type_str = "String";
                    break;
                default:
                    type_str = "Unknown";
                    break;
            }
            return "<pylibheif.HeifEncoderParameter name='" + self.name() + "' type=" + type_str +
                   ">";
        });

    nb::class_<HeifEncoder>(m, "HeifEncoder", nb::is_weak_referenceable())
        .def(nb::init<heif_compression_format, const std::string&>(), nb::arg("format"),
             nb::arg("preset") = "", nb::call_guard<nb::gil_scoped_release>())
        .def(nb::init<HeifEncoderDescriptor, const std::string&>(), nb::arg("descriptor"),
             nb::arg("preset") = "", nb::call_guard<nb::gil_scoped_release>())
        .def_prop_ro("name", &HeifEncoder::name)
        .def("set_lossy_quality", &HeifEncoder::set_lossy_quality)
        .def("set_lossless", &HeifEncoder::set_lossless)
        .def("set_parameter", &HeifEncoder::set_parameter)
        .def("get_parameter", &HeifEncoder::get_parameter)
        .def("has_parameter", &HeifEncoder::has_parameter, nb::arg("name"))
        .def("apply_preset", &HeifEncoder::apply_preset, nb::arg("preset"))
        .def("set_parameters", &HeifEncoder::set_parameters, nb::arg("params"))
        .def("set_integer_parameter", &HeifEncoder::set_integer_parameter)
        .def("get_integer_parameter", &HeifEncoder::get_integer_parameter)
        .def("set_boolean_parameter", &HeifEncoder::set_boolean_parameter)
        .def("get_boolean_parameter", &HeifEncoder::get_boolean_parameter)
        .def("set_string_parameter", &HeifEncoder::set_string_parameter)
        .def("get_string_parameter", &HeifEncoder::get_string_parameter)
        .def("_list_parameters", &HeifEncoder::list_parameters)
        .def("encode_image", &HeifEncoder::encode_image, nb::arg("ctx"), nb::arg("image"),
             nb::arg("preset") = "", nb::arg("options") = nb::none(),
             nb::call_guard<nb::gil_scoped_release>(), nb::keep_alive<0, 2>())
        .def("encode_thumbnail", &HeifEncoder::encode_thumbnail, nb::arg("ctx"), nb::arg("image"),
             nb::arg("master_image"), nb::arg("bbox_size"), nb::arg("options") = nb::none(),
             nb::call_guard<nb::gil_scoped_release>(), nb::keep_alive<0, 2>())
        .def("__repr__", [](const HeifEncoder& self) {
            return "<pylibheif.HeifEncoder name='" + self.name() + "'>";
        });

    m.attr("AUX_IMAGE_FILTER_OMIT_ALPHA") = nb::cast(LIBHEIF_AUX_IMAGE_FILTER_OMIT_ALPHA);

    m.attr("AUX_IMAGE_FILTER_OMIT_DEPTH") = nb::cast(LIBHEIF_AUX_IMAGE_FILTER_OMIT_DEPTH);

    m.def("get_default_num_threads", &get_default_num_codec_threads,
          "Get the global default number of threads used for decoding codecs.");
    m.def("set_default_num_threads", &set_default_num_codec_threads, nb::arg("threads"),
          "Set the global default number of threads used for decoding codecs (0 resets to adaptive "
          "default).");

    m.def("get_default_encoder_preset", &get_default_encoder_preset,
          "Get the global default encoder preset ('ultrafast', 'fast', 'balanced', 'quality').");
    m.def(
        "set_default_encoder_preset", &set_default_encoder_preset, nb::arg("preset"),
        "Set the global default encoder preset (empty string resets to balanced or env default).");

    m.def(
        "get_libheif_version", []() { return std::string(heif_get_version()); },
        "Get the underlying libheif library version string.");
    m.def(
        "get_libheif_version_number", []() { return heif_get_version_number(); },
        "Get the underlying libheif library version number integer.");
}