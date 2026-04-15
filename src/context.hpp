#pragma once
#include <memory>
#include <string>
#include <vector>

#include "common.hpp"

namespace pylibheif {

class HeifImageHandle;

class HeifContext {
   public:
    HeifContext();

    void read_from_file(const char* filename);
    void read_from_memory(const nb::bytes& data);

    std::shared_ptr<HeifImageHandle> get_primary_image_handle();
    std::vector<heif_item_id> get_list_of_top_level_image_IDs();
    std::shared_ptr<HeifImageHandle> get_image_handle(heif_item_id id);

    void write_to_file(const char* filename);
    nb::bytes write_to_bytes();

    // Metadata writing
    void add_exif_metadata(std::shared_ptr<HeifImageHandle> handle, const nb::bytes& data);
    void add_xmp_metadata(std::shared_ptr<HeifImageHandle> handle, const nb::bytes& data);
    void add_generic_metadata(std::shared_ptr<HeifImageHandle> handle, const nb::bytes& data,
                              const char* item_type, const char* content_type = "");

    heif_context* get() const { return ctx.get(); }

   private:
    ContextPtr ctx;
    // Store memory data to ensure it outlives the context
    nb::object memory_reference;
};

}  // namespace pylibheif
