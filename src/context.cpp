#include "context.hpp"

#include <libheif/heif_brands.h>
#include <libheif/heif_sequences.h>
#include <nanobind/nanobind.h>  // Ensure nanobind is included for gil_scoped_release
#include <nanobind/ndarray.h>

#include "image.hpp"
#include "track.hpp"

namespace pylibheif {

HeifContext::HeifContext() : state(std::make_shared<ContextState>()) {
    state->ctx.reset(heif_context_alloc());
}

void HeifContext::close() {
    if (state) {
        state->close_buffer();
        state->ctx.reset();
        state->is_closed = true;
    }
}

void HeifContext::reset() {
    if (!state) {
        state = std::make_shared<ContextState>();
    }
    state->close_buffer();
    state->ctx.reset(heif_context_alloc());
    state->is_closed = false;
}

void HeifContext::check_closed() const {
    if (!state || state->is_closed) {
        throw std::runtime_error("HeifContext has been closed");
    }
}

void HeifContext::read_from_file(const std::string& filename) {
    if (is_closed() || state->buffer_holder || state->memory_reference.is_valid()) {
        reset();
    }
    check_error(heif_context_read_from_file(state->ctx.get(), filename.c_str(), nullptr));
}

void HeifContext::read_from_memory(const nb::handle& data) {
    if (is_closed() || state->buffer_holder || state->memory_reference.is_valid()) {
        reset();
    }

    // Safely extract and lock buffer under the GIL
    state->buffer_holder = std::make_unique<PyBufferHolder>(data.ptr(), PyBUF_SIMPLE);
    state->memory_reference = nb::borrow(data);

    const char* data_ptr = static_cast<const char*>(state->buffer_holder->buf());
    size_t data_size = state->buffer_holder->len();

    nb::gil_scoped_release release;
    check_error(
        heif_context_read_from_memory_without_copy(state->ctx.get(), data_ptr, data_size, nullptr));
}

void HeifContext::read_from_stream(const nb::object& stream) {
    if (is_closed() || state->buffer_holder || state->memory_reference.is_valid() ||
        state->stream_reader) {
        reset();
    }

    if (!nb::hasattr(stream, "read")) {
        throw std::invalid_argument("Stream object must have a 'read' method");
    }

    // Set up PyStreamReader and anchor in ContextState for persistent lifetime
    state->stream_holder = stream;
    state->stream_reader = std::make_unique<PyStreamReader>(stream);

    state->reader_vtable = {};
    state->reader_vtable.reader_api_version = 1;
    state->reader_vtable.get_position = PyStreamReader::trampoline_get_position;
    state->reader_vtable.read = PyStreamReader::trampoline_read;
    state->reader_vtable.seek = PyStreamReader::trampoline_seek;
    state->reader_vtable.wait_for_file_size = PyStreamReader::trampoline_wait_for_file_size;

    nb::gil_scoped_release release;
    check_error(heif_context_read_from_reader(state->ctx.get(), &state->reader_vtable,
                                              state->stream_reader.get(), nullptr));
}

HeifImageHandle HeifContext::get_primary_image_handle() {
    check_closed();
    heif_image_handle* handle;
    check_error(heif_context_get_primary_image_handle(state->ctx.get(), &handle));
    return HeifImageHandle(handle, state);
}

std::vector<heif_item_id> HeifContext::get_list_of_top_level_image_IDs() {
    check_closed();
    int count = heif_context_get_number_of_top_level_images(state->ctx.get());
    std::vector<heif_item_id> ids(count);
    heif_context_get_list_of_top_level_image_IDs(state->ctx.get(), ids.data(), count);
    return ids;
}

HeifImageHandle HeifContext::get_image_handle(heif_item_id id) {
    check_closed();
    heif_image_handle* handle;
    check_error(heif_context_get_image_handle(state->ctx.get(), id, &handle));
    return HeifImageHandle(handle, state);
}

void HeifContext::write_to_file(const std::string& filename) {
    check_closed();
    check_error(heif_context_write_to_file(state->ctx.get(), filename.c_str()));
}

struct WriterData {
    std::vector<uint8_t> data;
};

static struct heif_error writer_write(struct heif_context* ctx, const void* data, size_t size,
                                      void* userdata) {
    (void)ctx;
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

static std::vector<uint8_t> encode_context_to_vector(heif_context* ctx) {
    WriterData wd;

    struct heif_writer writer = {};  // Zero-initialize all fields
    writer.writer_api_version = 1;
    writer.write = writer_write;

    {
        nb::gil_scoped_release release;

        // Estimate required size based on primary image dimensions to minimize reallocations
        ImageHandlePtr handle_guard;
        heif_image_handle* raw_handle = nullptr;
        heif_error err = heif_context_get_primary_image_handle(ctx, &raw_handle);
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

        check_error(heif_context_write(ctx, &writer, &wd));
    }

    return wd.data;
}

nb::object HeifContext::write_to_memoryview() {
    check_closed();
    std::vector<uint8_t> data = encode_context_to_vector(state->ctx.get());

    if (data.empty()) {
        PyObject* empty_mv = PyMemoryView_FromMemory(nullptr, 0, PyBUF_READ);
        if (!empty_mv) {
            throw nb::python_error();
        }
        return nb::steal<nb::object>(empty_mv);
    }

    auto* vec = new std::vector<uint8_t>(std::move(data));
    nb::capsule owner(vec, [](void* p) noexcept { delete static_cast<std::vector<uint8_t>*>(p); });

    nb::ndarray<nb::memview, const uint8_t, nb::shape<-1>, nb::c_contig> arr(vec->data(),
                                                                             {vec->size()}, owner);

    return nb::cast(arr);
}

nb::object HeifContext::write_to_bytes(bool copy) {
    if (!copy) {
        return write_to_memoryview();
    }
    check_closed();
    std::vector<uint8_t> data = encode_context_to_vector(state->ctx.get());
    return nb::bytes((const char*)data.data(), data.size());
}

void HeifContext::write_to_stream(const nb::object& stream) {
    check_closed();
    if (!nb::hasattr(stream, "write")) {
        throw std::invalid_argument("Stream object must have a 'write' method");
    }

    PyStreamWriter sw(stream);
    struct heif_writer writer = {};
    writer.writer_api_version = 1;
    writer.write = PyStreamWriter::trampoline_write;

    heif_error err;
    {
        nb::gil_scoped_release release;
        err = heif_context_write(state->ctx.get(), &writer, &sw);
    }

    if (err.code != heif_error_Ok) {
        sw.rethrow_if_exception();
        check_error(err);
    }

    heif_error flush_err = sw.flush();
    if (flush_err.code != heif_error_Ok) {
        sw.rethrow_if_exception();
        check_error(flush_err);
    }
}

void HeifContext::add_exif_metadata(const HeifImageHandle& handle, const nb::bytes& data) {
    check_closed();
    const char* ptr = data.c_str();
    int size = static_cast<int>(data.size());
    heif_context* ctx_ptr = state->ctx.get();
    heif_image_handle* h_ptr = handle.get();
    heif_error err;
    {
        nb::gil_scoped_release release;
        err = heif_context_add_exif_metadata(ctx_ptr, h_ptr, ptr, size);
    }
    check_error(err);
}

void HeifContext::add_xmp_metadata(const HeifImageHandle& handle, const nb::bytes& data) {
    check_closed();
    const char* ptr = data.c_str();
    int size = static_cast<int>(data.size());
    heif_context* ctx_ptr = state->ctx.get();
    heif_image_handle* h_ptr = handle.get();
    heif_error err;
    {
        nb::gil_scoped_release release;
        err = heif_context_add_XMP_metadata(ctx_ptr, h_ptr, ptr, size);
    }
    check_error(err);
}

void HeifContext::add_generic_metadata(const HeifImageHandle& handle, const nb::bytes& data,
                                       const std::string& item_type,
                                       const std::string& content_type) {
    check_closed();
    const char* ptr = data.c_str();
    int size = static_cast<int>(data.size());
    const char* type_str = item_type.c_str();
    const char* ct = content_type.empty() ? nullptr : content_type.c_str();
    heif_context* ctx_ptr = state->ctx.get();
    heif_image_handle* h_ptr = handle.get();
    heif_error err;
    {
        nb::gil_scoped_release release;
        err = heif_context_add_generic_metadata(ctx_ptr, h_ptr, ptr, size, type_str, ct);
    }
    check_error(err);
}

void HeifContext::assign_thumbnail(const HeifImageHandle& master_image,
                                   const HeifImageHandle& thumbnail_image) {
    check_closed();
    heif_context* ctx_ptr = state->ctx.get();
    heif_image_handle* master_ptr = master_image.get();
    heif_image_handle* thumb_ptr = thumbnail_image.get();
    heif_error err;
    {
        nb::gil_scoped_release release;
        // libheif's C API heif_context_assign_thumbnail inverts master/thumbnail when calling
        // internal HeifContext::assign_thumbnail. Passing (thumb_ptr, master_ptr) creates the
        // correct iref 'thmb' reference from thumbnail to master.
        err = heif_context_assign_thumbnail(ctx_ptr, thumb_ptr, master_ptr);
    }
    check_error(err);
}

void HeifContext::assign_auxiliary_image(const HeifImageHandle& master_image,
                                         const HeifImageHandle& auxiliary_image,
                                         const std::string& auxiliary_type) {
    check_closed();
    heif_context* ctx_ptr = state->ctx.get();
    heif_image_handle* master_ptr = master_image.get();
    heif_image_handle* aux_ptr = auxiliary_image.get();
    if (!master_ptr || !aux_ptr) {
        throw std::invalid_argument("Master and auxiliary image handles must not be null.");
    }
    if (auxiliary_type.empty()) {
        throw std::invalid_argument("Auxiliary type cannot be empty.");
    }
    heif_error err;
    {
        nb::gil_scoped_release release;
        err = heif_context_assign_auxiliary_image(ctx_ptr, master_ptr, aux_ptr,
                                                  auxiliary_type.c_str());
    }
    check_error(err);
}

void HeifContext::set_primary_image(const HeifImageHandle& handle) {
    check_closed();
    heif_image_handle* h_ptr = handle.get();
    if (!h_ptr) {
        throw std::invalid_argument("Cannot set null handle as primary image.");
    }
    heif_context* ctx_ptr = state->ctx.get();
    heif_error err;
    {
        nb::gil_scoped_release release;
        err = heif_context_set_primary_image(ctx_ptr, h_ptr);
    }
    check_error(err);
}

void HeifContext::set_major_brand(const std::string& brand) {
    check_closed();
    if (brand.size() != 4) {
        throw std::invalid_argument("Brand must be a 4-character string (FourCC).");
    }
    heif_brand2 b = heif_fourcc_to_brand(brand.c_str());
    heif_context_set_major_brand(state->ctx.get(), b);
}

void HeifContext::add_compatible_brand(const std::string& brand) {
    check_closed();
    if (brand.size() != 4) {
        throw std::invalid_argument("Brand must be a 4-character string (FourCC).");
    }
    heif_brand2 b = heif_fourcc_to_brand(brand.c_str());
    heif_context_add_compatible_brand(state->ctx.get(), b);
}

bool HeifContext::has_sequence() const {
    check_closed();
    return heif_context_has_sequence(state->ctx.get()) != 0;
}

uint32_t HeifContext::get_sequence_timescale() const {
    check_closed();
    return heif_context_get_sequence_timescale(state->ctx.get());
}

uint64_t HeifContext::get_sequence_duration() const {
    check_closed();
    return heif_context_get_sequence_duration(state->ctx.get());
}

int HeifContext::get_number_of_sequence_tracks() const {
    check_closed();
    if (!has_sequence()) return 0;
    return heif_context_number_of_sequence_tracks(state->ctx.get());
}

std::vector<uint32_t> HeifContext::get_sequence_track_ids() const {
    check_closed();
    int count = get_number_of_sequence_tracks();
    if (count <= 0) return {};
    std::vector<uint32_t> ids(count);
    heif_context_get_track_ids(state->ctx.get(), ids.data());
    return ids;
}

HeifTrack HeifContext::get_track(uint32_t track_id) {
    check_closed();
    if (!has_sequence()) {
        throw HeifInputDoesNotExistError("Context does not contain any image sequences.");
    }
    heif_track* t = heif_context_get_track(state->ctx.get(), track_id);
    if (!t) {
        throw HeifInputDoesNotExistError("Sequence track not found.");
    }
    uint32_t actual_id = heif_track_get_id(t);
    return HeifTrack(t, state, actual_id);
}

HeifTrack HeifContext::add_visual_sequence_track(uint16_t width, uint16_t height,
                                                 uint32_t track_type, uint32_t timescale) {
    check_closed();
    heif_track_options* track_opts = heif_track_options_alloc();
    if (track_opts) {
        heif_track_options_set_timescale(track_opts, timescale);
    }
    heif_track* out_track = nullptr;
    heif_error err = heif_context_add_visual_sequence_track(
        state->ctx.get(), width, height, track_type, track_opts, nullptr, &out_track);
    if (track_opts) {
        heif_track_options_release(track_opts);
    }
    check_error(err);
    if (!out_track) {
        throw std::runtime_error("Failed to create visual sequence track.");
    }
    uint32_t actual_id = heif_track_get_id(out_track);
    return HeifTrack(out_track, state, actual_id);
}

void HeifContext::set_sequence_timescale(uint32_t timescale) {
    check_closed();
    heif_context_set_sequence_timescale(state->ctx.get(), timescale);
}

void HeifContext::set_number_of_sequence_repetitions(uint32_t repetitions) {
    check_closed();
    heif_context_set_number_of_sequence_repetitions(state->ctx.get(), repetitions);
}

}  // namespace pylibheif
