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

class HeifError : public std::runtime_error {
   public:
    HeifError(const heif_error& err)
        : std::runtime_error(err.message), code(err.code), subcode(err.subcode) {}

    heif_error_code code;
    heif_suberror_code subcode;
};

inline void check_error(const heif_error& err) {
    if (err.code != heif_error_Ok) {
        throw HeifError(err);
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
