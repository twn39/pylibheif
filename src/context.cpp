#include "context.hpp"
#include "image.hpp"

namespace pylibheif {

HeifContext::HeifContext() { ctx = heif_context_alloc(); }

HeifContext::~HeifContext() {
  if (ctx) {
    heif_context_free(ctx);
  }
}

void HeifContext::read_from_file(const std::string &filename) {
  check_error(heif_context_read_from_file(ctx, filename.c_str(), nullptr));
}

void HeifContext::read_from_memory(const py::bytes &data) {
  memory_data =
      std::string(data); // Store in member to ensure data outlives context
  check_error(heif_context_read_from_memory_without_copy(
      ctx, memory_data.data(), memory_data.size(), nullptr));
}

std::shared_ptr<HeifImageHandle> HeifContext::get_primary_image_handle() {
  heif_image_handle *handle;
  check_error(heif_context_get_primary_image_handle(ctx, &handle));
  return std::make_shared<HeifImageHandle>(handle);
}

std::vector<heif_item_id> HeifContext::get_list_of_top_level_image_IDs() {
  int count = heif_context_get_number_of_top_level_images(ctx);
  std::vector<heif_item_id> ids(count);
  heif_context_get_list_of_top_level_image_IDs(ctx, ids.data(), count);
  return ids;
}

std::shared_ptr<HeifImageHandle>
HeifContext::get_image_handle(heif_item_id id) {
  heif_image_handle *handle;
  check_error(heif_context_get_image_handle(ctx, id, &handle));
  return std::make_shared<HeifImageHandle>(handle);
}

void HeifContext::write_to_file(const std::string &filename) {
  check_error(heif_context_write_to_file(ctx, filename.c_str()));
}

} // namespace pylibheif
