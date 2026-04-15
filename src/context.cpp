#include "context.hpp"

#include <nanobind/nanobind.h>  // Ensure nanobind is included for gil_scoped_release

#include "image.hpp"

namespace pylibheif {

HeifContext::HeifContext() : ctx(heif_context_alloc()) {}

void HeifContext::read_from_file(const char* filename) {
    check_error(heif_context_read_from_file(ctx.get(), filename, nullptr));
}

void HeifContext::read_from_memory(const nb::bytes& data) {
    if (memory_reference.is_valid()) {
        throw std::runtime_error("Context already initialized with memory data");
    }
    // Store in member to ensure data outlives context
    memory_reference = data;

    nb::gil_scoped_release release;
    check_error(
        heif_context_read_from_memory_without_copy(ctx.get(), data.c_str(), data.size(), nullptr));
}

std::shared_ptr<HeifImageHandle> HeifContext::get_primary_image_handle() {
    heif_image_handle* handle;
    check_error(heif_context_get_primary_image_handle(ctx.get(), &handle));
    return std::make_shared<HeifImageHandle>(handle);
}

std::vector<heif_item_id> HeifContext::get_list_of_top_level_image_IDs() {
    int count = heif_context_get_number_of_top_level_images(ctx.get());
    std::vector<heif_item_id> ids(count);
    heif_context_get_list_of_top_level_image_IDs(ctx.get(), ids.data(), count);
    return ids;
}

std::shared_ptr<HeifImageHandle> HeifContext::get_image_handle(heif_item_id id) {
    heif_image_handle* handle;
    check_error(heif_context_get_image_handle(ctx.get(), id, &handle));
    return std::make_shared<HeifImageHandle>(handle);
}

void HeifContext::write_to_file(const char* filename) {
    check_error(heif_context_write_to_file(ctx.get(), filename));
}

struct WriterData {
    std::vector<uint8_t> data;
};

static struct heif_error writer_write(struct heif_context* ctx, const void* data, size_t size,
                                      void* userdata) {
    try {
        WriterData* wd = (WriterData*)userdata;
        const uint8_t* bytes = (const uint8_t*)data;
        wd->data.insert(wd->data.end(), bytes, bytes + size);
    } catch (...) {
        struct heif_error err = {heif_error_Memory_allocation_error, heif_suberror_Unspecified,
                                 "Memory allocation failed during write"};
        return err;
    }

    struct heif_error err = {heif_error_Ok, heif_suberror_Unspecified, "Success"};
    return err;
}

nb::bytes HeifContext::write_to_bytes() {
    WriterData wd;
    wd.data.reserve(1024 * 1024);  // Pre-allocate 1MB to minimize reallocations

    struct heif_writer writer = {};  // Zero-initialize all fields
    writer.writer_api_version = 1;
    writer.write = writer_write;

    {
        nb::gil_scoped_release release;
        check_error(heif_context_write(ctx.get(), &writer, &wd));
    }

    return nb::bytes((char*)wd.data.data(), wd.data.size());
}

void HeifContext::add_exif_metadata(std::shared_ptr<HeifImageHandle> handle,
                                    const nb::bytes& data) {
    check_error(heif_context_add_exif_metadata(ctx.get(), handle->get(), data.c_str(),
                                               static_cast<int>(data.size())));
}

void HeifContext::add_xmp_metadata(std::shared_ptr<HeifImageHandle> handle, const nb::bytes& data) {
    check_error(heif_context_add_XMP_metadata(ctx.get(), handle->get(), data.c_str(),
                                              static_cast<int>(data.size())));
}

void HeifContext::add_generic_metadata(std::shared_ptr<HeifImageHandle> handle,
                                       const nb::bytes& data, const char* item_type,
                                       const char* content_type) {
    const char* ct = (content_type && content_type[0] != '\0') ? content_type : nullptr;
    check_error(heif_context_add_generic_metadata(ctx.get(), handle->get(), data.c_str(),
                                                  static_cast<int>(data.size()), item_type, ct));
}

}  // namespace pylibheif
