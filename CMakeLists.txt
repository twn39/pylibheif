cmake_minimum_required(VERSION 3.15)
project(pylibheif LANGUAGES C CXX)

# Find pybind11
find_package(pybind11 REQUIRED)

# libheif options
set(WITH_EXAMPLES OFF CACHE BOOL "Build examples")
set(WITH_RAV1E OFF CACHE BOOL "Build rav1e")
option(WITH_DAV1D "Build dav1d" ON)
option(WITH_AOM "Build aom" ON)
option(WITH_X265 "Build x265" ON)
option(WITH_LIBDE265 "Build libde265" ON)
option(WITH_OpenJPEG_ENCODER "Build OpenJPEG encoder" ON)
option(WITH_OpenJPEG_DECODER "Build OpenJPEG decoder" ON)
option(WITH_JPEG_ENCODER "Build JPEG encoder" ON)
option(WITH_JPEG_DECODER "Build JPEG decoder" ON)
option(WITH_X264 "Build x264 AVC encoder" ON)
option(WITH_OpenH264_DECODER "Build OpenH264 AVC decoder" ON)
option(WITH_FFMPEG_DECODER "Build FFmpeg HEVC/AVC decoder" OFF)

# Disable plugin mode - build codecs as built-in
set(WITH_DAV1D_PLUGIN OFF CACHE BOOL "Build dav1d as plugin" FORCE)
set(WITH_AOM_DECODER_PLUGIN OFF CACHE BOOL "Build AOM decoder as plugin" FORCE)
set(WITH_AOM_ENCODER_PLUGIN OFF CACHE BOOL "Build AOM encoder as plugin" FORCE)
set(WITH_OpenJPEG_ENCODER_PLUGIN OFF CACHE BOOL "Build OpenJPEG encoder as plugin" FORCE)
set(WITH_OpenJPEG_DECODER_PLUGIN OFF CACHE BOOL "Build OpenJPEG decoder as plugin" FORCE)
set(ENABLE_PLUGIN_LOADING OFF CACHE BOOL "Disable plugin loading" FORCE)

# Add libheif submodule
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build shared libraries" FORCE)
add_subdirectory(third_party/libheif)

# Define the extension module
pybind11_add_module(pylibheif
    src/main.cpp
    src/context.cpp
    src/image.cpp
    src/encoder.cpp
)

# Link with libheif
target_link_libraries(pylibheif PRIVATE heif)

# Include directories
target_include_directories(pylibheif PRIVATE
    src
    third_party/libheif/libheif/api
    ${CMAKE_CURRENT_BINARY_DIR}/third_party/libheif
)

# C++ standard
target_compile_features(pylibheif PRIVATE cxx_std_17)
target_compile_options(pylibheif PRIVATE -O3)

# Install the module
install(TARGETS pylibheif DESTINATION .)
