#pragma once
#include <Python.h>
#include <libheif/heif.h>
#include <nanobind/nanobind.h>

#include <stdexcept>
#include <string>

namespace nb = nanobind;

namespace pylibheif {

struct PyBufferHolder {
    Py_buffer view;
    bool active = false;

    PyBufferHolder(PyObject* obj, int flags) {
        if (PyObject_GetBuffer(obj, &view, flags) != 0) {
            throw nb::python_error();
        }
        active = true;
    }

    ~PyBufferHolder() {
        if (active) {
            PyBuffer_Release(&view);
        }
    }

    const void* buf() const { return view.buf; }
    size_t len() const { return view.len; }
};

inline const char* get_error_code_name(heif_error_code code) {
    switch (code) {
        case heif_error_Ok:
            return "Ok";
        case heif_error_Input_does_not_exist:
            return "InputDoesNotExist";
        case heif_error_Invalid_input:
            return "InvalidInput";
        case heif_error_Unsupported_filetype:
            return "UnsupportedFiletype";
        case heif_error_Unsupported_feature:
            return "UnsupportedFeature";
        case heif_error_Usage_error:
            return "UsageError";
        case heif_error_Memory_allocation_error:
            return "MemoryAllocationError";
        case heif_error_Decoder_plugin_error:
            return "DecoderPluginError";
        case heif_error_Encoder_plugin_error:
            return "EncoderPluginError";
        case heif_error_Encoding_error:
            return "EncodingError";
        case heif_error_Color_profile_does_not_exist:
            return "ColorProfileDoesNotExist";
        default:
            return "UnknownError";
    }
}

class HeifError : public std::runtime_error {
   public:
    HeifError(const heif_error& err)
        : std::runtime_error(std::string("[HeifError: ") + get_error_code_name(err.code) + "] " +
                             (err.message ? err.message : "")),
          code(err.code),
          subcode(err.subcode) {}

    HeifError(heif_error_code c, const std::string& msg = "",
              heif_suberror_code sc = heif_suberror_Unspecified)
        : std::runtime_error(std::string("[HeifError: ") + get_error_code_name(c) + "] " + msg),
          code(c),
          subcode(sc) {}

    heif_error_code code;
    heif_suberror_code subcode;
};

class HeifInputDoesNotExistError : public HeifError {
   public:
    HeifInputDoesNotExistError(const heif_error& err) : HeifError(err) {}
    HeifInputDoesNotExistError(const std::string& msg = "")
        : HeifError(heif_error_Input_does_not_exist, msg) {}
};

class HeifInvalidInputError : public HeifError {
   public:
    HeifInvalidInputError(const heif_error& err) : HeifError(err) {}
    HeifInvalidInputError(const std::string& msg = "") : HeifError(heif_error_Invalid_input, msg) {}
};

class HeifUnsupportedFiletypeError : public HeifError {
   public:
    HeifUnsupportedFiletypeError(const heif_error& err) : HeifError(err) {}
    HeifUnsupportedFiletypeError(const std::string& msg = "")
        : HeifError(heif_error_Unsupported_filetype, msg) {}
};

class HeifUnsupportedFeatureError : public HeifError {
   public:
    HeifUnsupportedFeatureError(const heif_error& err) : HeifError(err) {}
    HeifUnsupportedFeatureError(const std::string& msg = "")
        : HeifError(heif_error_Unsupported_feature, msg) {}
};

class HeifUsageError : public HeifError {
   public:
    HeifUsageError(const heif_error& err) : HeifError(err) {}
    HeifUsageError(const std::string& msg = "") : HeifError(heif_error_Usage_error, msg) {}
};

class HeifMemoryAllocationError : public HeifError {
   public:
    HeifMemoryAllocationError(const heif_error& err) : HeifError(err) {}
    HeifMemoryAllocationError(const std::string& msg = "")
        : HeifError(heif_error_Memory_allocation_error, msg) {}
};

class HeifEncodingError : public HeifError {
   public:
    HeifEncodingError(const heif_error& err) : HeifError(err) {}
    HeifEncodingError(const std::string& msg = "") : HeifError(heif_error_Encoding_error, msg) {}
};

class HeifColorProfileDoesNotExistError : public HeifError {
   public:
    HeifColorProfileDoesNotExistError(const heif_error& err) : HeifError(err) {}
    HeifColorProfileDoesNotExistError(const std::string& msg = "")
        : HeifError(heif_error_Color_profile_does_not_exist, msg) {}
};

inline void check_error(const heif_error& err) {
    if (err.code != heif_error_Ok) {
        switch (err.code) {
            case heif_error_Input_does_not_exist:
                throw HeifInputDoesNotExistError(err);
            case heif_error_Invalid_input:
                throw HeifInvalidInputError(err);
            case heif_error_Unsupported_filetype:
                throw HeifUnsupportedFiletypeError(err);
            case heif_error_Unsupported_feature:
                throw HeifUnsupportedFeatureError(err);
            case heif_error_Usage_error:
                throw HeifUsageError(err);
            case heif_error_Memory_allocation_error:
                throw HeifMemoryAllocationError(err);
            case heif_error_Encoding_error:
                throw HeifEncodingError(err);
            case heif_error_Color_profile_does_not_exist:
                throw HeifColorProfileDoesNotExistError(err);
            default:
                throw HeifError(err);
        }
    }
}

struct HeifContextDeleter {
    void operator()(heif_context* p) const {
        if (p) heif_context_free(p);
    }
};
struct HeifImageHandleDeleter {
    void operator()(heif_image_handle* p) const {
        if (p) heif_image_handle_release(p);
    }
};
struct HeifImageDeleter {
    void operator()(heif_image* p) const {
        if (p) heif_image_release(p);
    }
};
struct HeifEncoderDeleter {
    void operator()(heif_encoder* p) const {
        if (p) heif_encoder_release(p);
    }
};

using ContextPtr = std::unique_ptr<heif_context, HeifContextDeleter>;
using ImageHandlePtr = std::unique_ptr<heif_image_handle, HeifImageHandleDeleter>;
using ImagePtr = std::unique_ptr<heif_image, HeifImageDeleter>;
using EncoderPtr = std::unique_ptr<heif_encoder, HeifEncoderDeleter>;

}  // namespace pylibheif
