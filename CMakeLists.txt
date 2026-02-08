cmake_minimum_required(VERSION 3.15)
project(pylibheif LANGUAGES C CXX)

# Enable LTO if supported (reduces binary size, improves performance)
include(CheckIPOSupported)
check_ipo_supported(RESULT result OUTPUT output)
if(result)
    set(CMAKE_INTERPROCEDURAL_OPTIMIZATION ON)
endif()

# Set default visibility to hidden (reduces binary size)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)

# Find pybind11
find_package(pybind11 REQUIRED)

# libheif options
set(WITH_EXAMPLES OFF CACHE BOOL "Build examples")
set(WITH_RAV1E OFF CACHE BOOL "Build rav1e")
option(WITH_DAV1D "Build dav1d" ON)
option(WITH_SvtEnc "Build SVT-AV1" OFF)
option(WITH_AOM "Build aom" ON)
option(WITH_X265 "Build x265" ON)
option(WITH_KVAZAAR "Build Kvazaar" ON)
option(WITH_LIBDE265 "Build libde265" ON)
option(WITH_OpenJPEG_ENCODER "Build OpenJPEG encoder" ON)
option(WITH_OpenJPEG_DECODER "Build OpenJPEG decoder" ON)
option(WITH_JPEG_ENCODER "Build JPEG encoder" ON)
option(WITH_JPEG_DECODER "Build JPEG decoder" ON)
option(WITH_X264 "Build x264 AVC encoder" OFF)
option(WITH_OpenH264_DECODER "Build OpenH264 AVC decoder" OFF)
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
target_compile_definitions(kvazaar PUBLIC KVZ_STATIC_LIB)

# Help libheif find Kvazaar from submodule
set(kvazaar_FOUND TRUE CACHE BOOLEAN "Kvazaar found" FORCE)
set(KVAZAAR_FOUND TRUE CACHE BOOLEAN "Kvazaar found" FORCE)
set(KVAZAAR_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/third_party/kvazaar/src" CACHE PATH "Kvazaar include dir" FORCE)
set(KVAZAAR_LIBRARY kvazaar CACHE STRING "Kvazaar library" FORCE)
set(KVAZAAR_LIBRARIES $<BUILD_INTERFACE:kvazaar> CACHE STRING "Kvazaar libraries" FORCE)

# Add libheif submodule
add_subdirectory(third_party/libheif EXCLUDE_FROM_ALL)

# Define the extension module
pybind11_add_module(_pylibheif
    src/main.cpp
    src/context.cpp
    src/image.cpp
    src/encoder.cpp
)

# Link with libheif
target_link_libraries(_pylibheif PRIVATE heif)

# Define macro for static kvazaar linking
target_compile_definitions(_pylibheif PRIVATE KVZ_STATIC_LIB)

# Include directories
target_include_directories(_pylibheif PRIVATE
    src
    third_party/libheif/libheif/api
    ${CMAKE_CURRENT_BINARY_DIR}/third_party/libheif
)

# C++ standard
target_compile_features(_pylibheif PRIVATE cxx_std_17)

# Compiler optimizations
if(MSVC)
    target_compile_options(_pylibheif PRIVATE /O2)
else()
    target_compile_options(_pylibheif PRIVATE -O3)
endif()

# Install the module
install(TARGETS _pylibheif DESTINATION pylibheif)
