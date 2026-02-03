#include "image.hpp"

namespace pylibheif {

HeifImageHandle::~HeifImageHandle() {
  if (handle) {
    heif_image_handle_release(handle);
  }
}

int HeifImageHandle::get_width() const {
  return heif_image_handle_get_width(handle);
}

int HeifImageHandle::get_height() const {
  return heif_image_handle_get_height(handle);
}

bool HeifImageHandle::has_alpha_channel() const {
  return heif_image_handle_has_alpha_channel(handle);
}

int HeifImageHandle::get_luma_bits_per_pixel() const {
  return heif_image_handle_get_luma_bits_per_pixel(handle);
}

int HeifImageHandle::get_chroma_bits_per_pixel() const {
  return heif_image_handle_get_chroma_bits_per_pixel(handle);
}

std::shared_ptr<HeifImage> HeifImageHandle::decode(heif_colorspace colorspace,
                                                   heif_chroma chroma) {
  heif_image *img;
  check_error(heif_decode_image(handle, &img, colorspace, chroma, nullptr));
  return std::make_shared<HeifImage>(img);
}

std::vector<heif_item_id> HeifImageHandle::get_list_of_metadata_block_IDs(
    const std::string &type_filter) {
  int count = heif_image_handle_get_number_of_metadata_blocks(
      handle, type_filter.empty() ? nullptr : type_filter.c_str());
  std::vector<heif_item_id> ids(count);
  heif_image_handle_get_list_of_metadata_block_IDs(
      handle, type_filter.empty() ? nullptr : type_filter.c_str(), ids.data(),
      count);
  return ids;
}

std::string HeifImageHandle::get_metadata_block_type(heif_item_id id) {
  return heif_image_handle_get_metadata_type(handle, id);
}

py::bytes HeifImageHandle::get_metadata_block(heif_item_id id) {
  size_t size = heif_image_handle_get_metadata_size(handle, id);
  std::vector<uint8_t> data(size);
  check_error(heif_image_handle_get_metadata(handle, id, data.data()));
  return py::bytes((char *)data.data(), size);
}

HeifImage::HeifImage(int width, int height, heif_colorspace colorspace,
                     heif_chroma chroma) {
  check_error(heif_image_create(width, height, colorspace, chroma, &image));
}

HeifImage::~HeifImage() {
  if (image) {
    heif_image_release(image);
  }
}

int HeifImage::get_width(heif_channel channel) const {
  return heif_image_get_width(image, channel);
}

int HeifImage::get_height(heif_channel channel) const {
  return heif_image_get_height(image, channel);
}

void HeifImage::add_plane(heif_channel channel, int width, int height,
                          int bit_depth) {
  check_error(heif_image_add_plane(image, channel, width, height, bit_depth));
}

py::buffer_info HeifImage::get_buffer_info(heif_channel channel,
                                           bool writeable) {
  int stride;
  uint8_t *data;
  if (writeable) {
    data = heif_image_get_plane(image, channel, &stride);
  } else {
    data = const_cast<uint8_t *>(
        heif_image_get_plane_readonly(image, channel, &stride));
  }

  if (!data) {
    throw std::runtime_error("Failed to get image plane data");
  }

  int width = heif_image_get_width(image, channel);
  int height = heif_image_get_height(image, channel);
  int bpp_per_channel = heif_image_get_bits_per_pixel_range(image, channel);

  // Determine number of channels for interleaved formats
  int num_channels = 1;
  heif_chroma chroma = heif_image_get_chroma_format(image);
  if (chroma == heif_chroma_interleaved_RGB) {
    num_channels = 3;
  } else if (chroma == heif_chroma_interleaved_RGBA ||
             chroma == heif_chroma_interleaved_RRGGBB_BE ||
             chroma == heif_chroma_interleaved_RRGGBB_LE ||
             chroma == heif_chroma_interleaved_RRGGBBAA_BE ||
             chroma == heif_chroma_interleaved_RRGGBBAA_LE) {
    num_channels = 4;
  }

  size_t bytes_per_channel = (bpp_per_channel + 7) / 8;
  std::string format = (bytes_per_channel == 1)
                           ? py::format_descriptor<uint8_t>::format()
                           : py::format_descriptor<uint16_t>::format();

  if (num_channels > 1) {
    // Interleaved format: return 3D array (height, width, channels)
    return py::buffer_info(
        data, bytes_per_channel, format, 3,
        {(size_t)height, (size_t)width, (size_t)num_channels},
        {(size_t)stride, (size_t)(num_channels * bytes_per_channel),
         bytes_per_channel},
        !writeable);
  } else {
    // Single channel: return 2D array (height, width)
    return py::buffer_info(data, bytes_per_channel, format, 2,
                           {(size_t)height, (size_t)width},
                           {(size_t)stride, bytes_per_channel}, !writeable);
  }
}

} // namespace pylibheif
