#pragma once
#include <memory>
#include <string>
#include <vector>

#include "common.hpp"
#include "io_bridge.hpp"

namespace pylibheif {

class HeifImageHandle;
class HeifTrack;

struct ContextState {
    ContextPtr ctx;
    // Store memory data to ensure it outlives the context
    nb::object memory_reference;
    bool is_closed = false;
    std::unique_ptr<PyBufferHolder> buffer_holder;

    // Stream reader and holder
    std::unique_ptr<PyStreamReader> stream_reader;
    struct heif_reader reader_vtable{};
    nb::object stream_holder;

    ~ContextState() { close_buffer(); }

    void close_buffer() {
        if (buffer_holder || memory_reference.is_valid() || stream_holder.is_valid() ||
            stream_reader) {
            nb::gil_scoped_acquire acquire;
            buffer_holder.reset();
            memory_reference = nb::object();
            stream_reader.reset();
            stream_holder = nb::object();
        }
    }
};

class HeifContext {
   public:
    HeifContext();

    void close();
    void reset();

    void read_from_file(const std::string& filename);
    void read_from_memory(const nb::handle& data);
    void read_from_stream(const nb::object& stream);

    HeifImageHandle get_primary_image_handle();
    std::vector<heif_item_id> get_list_of_top_level_image_IDs();
    HeifImageHandle get_image_handle(heif_item_id id);

    void write_to_file(const std::string& filename);
    nb::object write_to_bytes(bool copy = true);
    nb::object write_to_memoryview();
    void write_to_stream(const nb::object& stream);

    // Metadata writing
    void add_exif_metadata(const HeifImageHandle& handle, const nb::bytes& data);
    void add_xmp_metadata(const HeifImageHandle& handle, const nb::bytes& data);
    void add_generic_metadata(const HeifImageHandle& handle, const nb::bytes& data,
                              const std::string& item_type, const std::string& content_type = "");

    void assign_thumbnail(const HeifImageHandle& master_image,
                          const HeifImageHandle& thumbnail_image);

    void set_primary_image(const HeifImageHandle& handle);
    void set_major_brand(const std::string& brand);
    void add_compatible_brand(const std::string& brand);

    // Sequence & Track APIs
    bool has_sequence() const;
    uint32_t get_sequence_timescale() const;
    uint64_t get_sequence_duration() const;
    int get_number_of_sequence_tracks() const;
    std::vector<uint32_t> get_sequence_track_ids() const;
    HeifTrack get_track(uint32_t track_id = 0);
    HeifTrack add_visual_sequence_track(uint16_t width, uint16_t height,
                                        uint32_t track_type = 0x76696465,
                                        uint32_t timescale = 1000);
    void set_sequence_timescale(uint32_t timescale);
    void set_number_of_sequence_repetitions(uint32_t repetitions);

    heif_context* get() const { return state ? state->ctx.get() : nullptr; }
    bool is_closed() const { return !state || state->is_closed; }
    std::shared_ptr<ContextState> get_state() const { return state; }

   private:
    void check_closed() const;

    std::shared_ptr<ContextState> state;
};

}  // namespace pylibheif
