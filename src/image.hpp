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

    int get_width() const;
    int get_height() const;
    bool has_alpha_channel() const;
    int get_luma_bits_per_pixel() const;
    int get_chroma_bits_per_pixel() const;

    std::shared_ptr<HeifImage> decode(heif_colorspace colorspace, heif_chroma chroma);

    // Metadata
    std::vector<heif_item_id> get_list_of_metadata_block_IDs(const char* type_filter = "");
    std::string get_metadata_block_type(heif_item_id id);
    nb::bytes get_metadata_block(heif_item_id id);

    heif_image_handle* get() const { return handle.get(); }

   private:
    ImageHandlePtr handle;
};

class HeifImage {
   public:
    HeifImage(heif_image* img) : image(img) {}
    HeifImage(int width, int height, heif_colorspace colorspace, heif_chroma chroma);

    int get_width(heif_channel channel) const;
    int get_height(heif_channel channel) const;
    void add_plane(heif_channel channel, int width, int height, int bit_depth);

    // Array sequence support
    nb::object get_array(heif_channel channel, bool writeable = false,
                         nb::handle owner = nb::handle());

    heif_image* get() const { return image.get(); }

   private:
    ImagePtr image;
};

}  // namespace pylibheif
