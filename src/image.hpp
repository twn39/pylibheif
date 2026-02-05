#pragma once
#include <map>
#include <memory>
#include <vector>

#include "common.hpp"

namespace pylibheif {

class HeifImage;

class HeifImageHandle {
   public:
    HeifImageHandle(heif_image_handle* h) : handle(h) {}
    ~HeifImageHandle();

    int get_width() const;
    int get_height() const;
    bool has_alpha_channel() const;
    int get_luma_bits_per_pixel() const;
    int get_chroma_bits_per_pixel() const;

    std::shared_ptr<HeifImage> decode(heif_colorspace colorspace, heif_chroma chroma);

    // Metadata
    std::vector<heif_item_id> get_list_of_metadata_block_IDs(const std::string& type_filter = "");
    std::string get_metadata_block_type(heif_item_id id);
    py::bytes get_metadata_block(heif_item_id id);

    heif_image_handle* get() const { return handle; }

   private:
    heif_image_handle* handle;
};

class HeifImage {
   public:
    HeifImage(heif_image* img) : image(img) {}
    HeifImage(int width, int height, heif_colorspace colorspace, heif_chroma chroma);
    ~HeifImage();

    int get_width(heif_channel channel) const;
    int get_height(heif_channel channel) const;
    void add_plane(heif_channel channel, int width, int height, int bit_depth);

    // Buffer protocol support
    py::buffer_info get_buffer_info(heif_channel channel, bool writeable = false);

    heif_image* get() const { return image; }

   private:
    heif_image* image;
};

}  // namespace pylibheif
