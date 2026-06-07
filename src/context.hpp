#pragma once
#include <memory>
#include <string>
#include <vector>

#include "common.hpp"

namespace pylibheif {

class HeifImageHandle;

struct ContextState {
    ContextPtr ctx;
    // Store memory data to ensure it outlives the context
    nb::object memory_reference;
    bool is_closed = false;
    std::unique_ptr<PyBufferHolder> buffer_holder;

    ~ContextState() {
        close_buffer();
    }

    void close_buffer() {
        if (buffer_holder) {
            nb::gil_scoped_acquire acquire;
            buffer_holder.reset();
        }
        if (memory_reference.is_valid()) {
            nb::gil_scoped_acquire acquire;
            memory_reference = nb::object();
        }
    }
};

class HeifContext {
   public:
    HeifContext();

    void close();

    void read_from_file(const std::string& filename);
    void read_from_memory(const nb::handle& data);

    HeifImageHandle get_primary_image_handle();
    std::vector<heif_item_id> get_list_of_top_level_image_IDs();
    HeifImageHandle get_image_handle(heif_item_id id);

    void write_to_file(const std::string& filename);
    nb::bytes write_to_bytes();

    // Metadata writing
    void add_exif_metadata(const HeifImageHandle& handle, const nb::bytes& data);
    void add_xmp_metadata(const HeifImageHandle& handle, const nb::bytes& data);
    void add_generic_metadata(const HeifImageHandle& handle, const nb::bytes& data,
                              const std::string& item_type, const std::string& content_type = "");

    heif_context* get() const { return state ? state->ctx.get() : nullptr; }
    bool is_closed() const { return !state || state->is_closed; }
    std::shared_ptr<ContextState> get_state() const { return state; }

   private:
    void check_closed() const;

    std::shared_ptr<ContextState> state;
};

}  // namespace pylibheif
