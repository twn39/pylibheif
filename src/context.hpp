#pragma once
#include "common.hpp"
#include <memory>
#include <string>
#include <vector>

namespace pylibheif {

class HeifImageHandle;

class HeifContext {
public:
  HeifContext();
  ~HeifContext();

  void read_from_file(const std::string &filename);
  void read_from_memory(const py::bytes &data);

  std::shared_ptr<HeifImageHandle> get_primary_image_handle();
  std::vector<heif_item_id> get_list_of_top_level_image_IDs();
  std::shared_ptr<HeifImageHandle> get_image_handle(heif_item_id id);

  void write_to_file(const std::string &filename);
  py::bytes write_to_bytes();

  // Metadata writing
  void add_exif_metadata(std::shared_ptr<HeifImageHandle> handle,
                         const py::bytes &data);
  void add_xmp_metadata(std::shared_ptr<HeifImageHandle> handle,
                        const py::bytes &data);
  void add_generic_metadata(std::shared_ptr<HeifImageHandle> handle,
                            const py::bytes &data, const std::string &item_type,
                            const std::string &content_type);

  heif_context *get() { return ctx; }

private:
  heif_context *ctx;
  // Store memory data to ensure it outlives the context
  std::string memory_data;
};

} // namespace pylibheif
