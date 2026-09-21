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

# Add nanobind submodule
find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
add_subdirectory(third_party/nanobind)

# libheif options
set(WITH_GDK_PIXBUF OFF CACHE BOOL "Build gdk-pixbuf plugin")
set(BUILD_TESTING OFF CACHE BOOL "Build tests")
set(BUILD_DOCUMENTATION OFF CACHE BOOL "Build documentation")

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
set(USE_RANGE_EXTENSION ON CACHE BOOL "Use range extension to enable 4:4:4 and 4:2:2 subsampling" FORCE)
add_subdirectory(third_party/kvazaar EXCLUDE_FROM_ALL)
target_compile_definitions(kvazaar PUBLIC KVZ_STATIC_LIB KVZ_RANGE_EXTENSION)

# Help libheif find Kvazaar from submodule
set(kvazaar_FOUND TRUE CACHE BOOL "Kvazaar found" FORCE)
set(KVAZAAR_FOUND TRUE CACHE BOOL "Kvazaar found" FORCE)
set(KVAZAAR_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/third_party/kvazaar/src" CACHE PATH "Kvazaar include dir" FORCE)
set(KVAZAAR_LIBRARY kvazaar CACHE STRING "Kvazaar library" FORCE)
set(KVAZAAR_LIBRARIES $<BUILD_INTERFACE:kvazaar> CACHE STRING "Kvazaar libraries" FORCE)

# Apply patches to bundled libheif submodule if needed
find_package(Git QUIET)
if(GIT_FOUND)
  file(GLOB LIBHEIF_PATCHES "${CMAKE_CURRENT_SOURCE_DIR}/patches/libheif/*.patch")
  list(SORT LIBHEIF_PATCHES)
  foreach(_patch_file IN LISTS LIBHEIF_PATCHES)
    get_filename_component(_patch_name "${_patch_file}" NAME)
    execute_process(
      COMMAND ${GIT_EXECUTABLE} apply --check "${_patch_file}"
      WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/third_party/libheif"
      RESULT_VARIABLE _patch_check
      OUTPUT_QUIET
      ERROR_QUIET
    )
    if(_patch_check EQUAL 0)
      message(STATUS "Applying ${_patch_name} to third_party/libheif...")
      execute_process(
        COMMAND ${GIT_EXECUTABLE} apply "${_patch_file}"
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/third_party/libheif"
        RESULT_VARIABLE _patch_apply
      )
      if(NOT _patch_apply EQUAL 0)
        message(WARNING "Failed to apply ${_patch_name} to third_party/libheif")
      endif()
    endif()
  endforeach()
endif()

# Add libheif submodule
add_subdirectory(third_party/libheif EXCLUDE_FROM_ALL)

# Define the extension module with isolated nanobind domain
nanobind_add_module(_pylibheif
    NB_DOMAIN pylibheif
    src/main.cpp
    src/bindings_image.cpp
    src/context.cpp
    src/image.cpp
    src/encoder.cpp
    src/track.cpp
)

# Link with libheif
target_link_libraries(_pylibheif PRIVATE heif)

# Symbol isolation: only export PyInit__pylibheif to prevent symbol leakage and conflicts
if(APPLE)
    target_link_options(_pylibheif PRIVATE -Wl,-exported_symbol,_PyInit__pylibheif)
elseif(UNIX AND NOT APPLE)
    target_link_options(_pylibheif PRIVATE
        -Wl,--exclude-libs,ALL
        -Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/src/module.sym
    )
endif()

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

# Compiler optimizations and warnings
if(MSVC)
    target_compile_options(_pylibheif PRIVATE /O2 /W4)
else()
    target_compile_options(_pylibheif PRIVATE -O3 -Wall -Wextra -Wpedantic)
endif()

# Install the module
install(TARGETS _pylibheif DESTINATION pylibheif)

