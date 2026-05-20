#include "context.hpp"

#include <nanobind/nanobind.h>  // Ensure nanobind is included for gil_scoped_release

#include "image.hpp"

namespace pylibheif {

HeifContext::HeifContext() : state(std::make_shared<ContextState>()) {
    state->ctx.reset(heif_context_alloc());
}

void HeifContext::close() {
    if (state) {
        state->ctx.reset();
        state->memory_reference = nb::object();
        state->is_closed = true;
    }
}

void HeifContext::check_closed() const {
    if (!state || state->is_closed) {
        throw std::runtime_error("HeifContext has been closed");
    }
}

void HeifContext::read_from_file(const char* filename) {
    check_closed();
    check_error(heif_context_read_from_file(state->ctx.get(), filename, nullptr));
}

void HeifContext::read_from_memory(const nb::handle& data) {
    check_closed();
    if (state->memory_reference.is_valid()) {
        throw std::runtime_error("Context already initialized with memory data");
    }
    
    // Safely extract buffer under the GIL
    PyBufferHolder buffer(data.ptr(), PyBUF_SIMPLE);
    
    // Store in member to ensure data outlives context
    state->memory_reference = nb::borrow(data);

    const char* data_ptr = static_cast<const char*>(buffer.buf());
    size_t data_size = buffer.len();

    nb::gil_scoped_release release;
    check_error(
        heif_context_read_from_memory_without_copy(state->ctx.get(), data_ptr, data_size, nullptr));
}

std::shared_ptr<HeifImageHandle> HeifContext::get_primary_image_handle() {
    check_closed();
    heif_image_handle* handle;
    check_error(heif_context_get_primary_image_handle(state->ctx.get(), &handle));
    return std::make_shared<HeifImageHandle>(handle, state);
}

std::vector<heif_item_id> HeifContext::get_list_of_top_level_image_IDs() {
    check_closed();
    int count = heif_context_get_number_of_top_level_images(state->ctx.get());
    std::vector<heif_item_id> ids(count);
    heif_context_get_list_of_top_level_image_IDs(state->ctx.get(), ids.data(), count);
    return ids;
}

std::shared_ptr<HeifImageHandle> HeifContext::get_image_handle(heif_item_id id) {
    check_closed();
    heif_image_handle* handle;
    check_error(heif_context_get_image_handle(state->ctx.get(), id, &handle));
    return std::make_shared<HeifImageHandle>(handle, state);
}

void HeifContext::write_to_file(const char* filename) {
    check_closed();
    check_error(heif_context_write_to_file(state->ctx.get(), filename));
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
    check_closed();
    WriterData wd;

    struct heif_writer writer = {};  // Zero-initialize all fields
    writer.writer_api_version = 1;
    writer.write = writer_write;

    {
        nb::gil_scoped_release release;

        // Estimate required size based on primary image dimensions to minimize reallocations
        ImageHandlePtr handle_guard;
        heif_image_handle* raw_handle = nullptr;
        heif_error err = heif_context_get_primary_image_handle(state->ctx.get(), &raw_handle);
        if (err.code == heif_error_Ok && raw_handle) {
            handle_guard.reset(raw_handle);
            int width = heif_image_handle_get_width(handle_guard.get());
            int height = heif_image_handle_get_height(handle_guard.get());

            // Heuristic: ~0.5 bytes per pixel (4 bits per pixel) is typical for HEVC/AV1.
            size_t estimated_size = static_cast<size_t>(width) * height / 2;

            // Clamp between 4KB and 100MB
            if (estimated_size < 4096)
                estimated_size = 4096;
            else if (estimated_size > 100 * 1024 * 1024)
                estimated_size = 100 * 1024 * 1024;

            wd.data.reserve(estimated_size);
        } else {
            wd.data.reserve(1024 * 1024);  // Fallback to 1MB
        }

        check_error(heif_context_write(state->ctx.get(), &writer, &wd));
    }

    return nb::bytes((char*)wd.data.data(), wd.data.size());
}

void HeifContext::add_exif_metadata(std::shared_ptr<HeifImageHandle> handle,
                                    const nb::bytes& data) {
    check_closed();
    check_error(heif_context_add_exif_metadata(state->ctx.get(), handle->get(), data.c_str(),
                                               static_cast<int>(data.size())));
}

void HeifContext::add_xmp_metadata(std::shared_ptr<HeifImageHandle> handle, const nb::bytes& data) {
    check_closed();
    check_error(heif_context_add_XMP_metadata(state->ctx.get(), handle->get(), data.c_str(),
                                              static_cast<int>(data.size())));
}

void HeifContext::add_generic_metadata(std::shared_ptr<HeifImageHandle> handle,
                                       const nb::bytes& data, const char* item_type,
                                       const char* content_type) {
    check_closed();
    const char* ct = (content_type && content_type[0] != '\0') ? content_type : nullptr;
    check_error(heif_context_add_generic_metadata(state->ctx.get(), handle->get(), data.c_str(),
                                                  static_cast<int>(data.size()), item_type, ct));
}

}  // namespace pylibheif
