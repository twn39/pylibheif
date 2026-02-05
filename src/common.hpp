#pragma once
#include <libheif/heif.h>
#include <pybind11/pybind11.h>

#include <stdexcept>
#include <string>

namespace py = pybind11;

namespace pylibheif {

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

}  // namespace pylibheif
