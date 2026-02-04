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
option(WITH_KVAZAAR "Build Kvazaar" ON)
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

# Add Kvazaar submodule
set(KVAZAAR_EXECUTABLE OFF CACHE BOOL "Build kvazaar executable" FORCE)
set(BUILD_KVAZAAR_BINARY OFF CACHE BOOL "Build kvazaar binary" FORCE)
set(BUILD_TESTS OFF CACHE BOOL "Build tests" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build shared libraries" FORCE)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
add_subdirectory(third_party/kvazaar EXCLUDE_FROM_ALL)

# Help libheif find Kvazaar from submodule
set(kvazaar_FOUND TRUE CACHE BOOLEAN "Kvazaar found" FORCE)
set(KVAZAAR_FOUND TRUE CACHE BOOLEAN "Kvazaar found" FORCE)
set(KVAZAAR_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/third_party/kvazaar/src" CACHE PATH "Kvazaar include dir" FORCE)
set(KVAZAAR_LIBRARY kvazaar CACHE STRING "Kvazaar library" FORCE)
set(KVAZAAR_LIBRARIES $<BUILD_INTERFACE:kvazaar> CACHE STRING "Kvazaar libraries" FORCE)

# Add libheif submodule
add_subdirectory(third_party/libheif EXCLUDE_FROM_ALL)

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

# Compiler optimizations
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(pylibheif PRIVATE -O3 -march=native -mtune=native)
else()
    target_compile_options(pylibheif PRIVATE -O3)
endif()

# Install the module
install(TARGETS pylibheif DESTINATION .)
