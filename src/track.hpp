#pragma once
#include <libheif/heif.h>
#include <libheif/heif_sequences.h>

#include <memory>
#include <optional>
#include <utility>
#include <vector>

#include "common.hpp"

namespace pylibheif {

struct ContextState;
class HeifImage;
class HeifEncoder;
class HeifDecodingOptions;

class HeifTrack {
   public:
    HeifTrack(heif_track* track, std::shared_ptr<ContextState> state, uint32_t track_id);
    ~HeifTrack() = default;

    // Move-only wrapper
    HeifTrack(const HeifTrack&) = delete;
    HeifTrack& operator=(const HeifTrack&) = delete;
    HeifTrack(HeifTrack&&) noexcept = default;
    HeifTrack& operator=(HeifTrack&&) noexcept = default;

    uint32_t id() const;
    heif_track_type track_type() const;
    uint32_t timescale() const;
    uint32_t number_of_repetitions() const;
    std::pair<uint16_t, uint16_t> resolution() const;
    bool has_alpha_channel() const;

    void encode_sequence_image(const HeifImage& image, HeifEncoder& encoder,
                               bool save_alpha = false);
    void encode_end_of_sequence(HeifEncoder& encoder);

    std::optional<HeifImage> decode_next_image(heif_colorspace colorspace = heif_colorspace_RGB,
                                               heif_chroma chroma = heif_chroma_undefined,
                                               const HeifDecodingOptions* options = nullptr);

    void rewind();

    heif_track* get() const { return m_track.get(); }
    std::shared_ptr<ContextState> get_state() const { return m_state; }

   private:
    std::unique_ptr<heif_track, decltype(&heif_track_release)> m_track;
    std::shared_ptr<ContextState> m_state;
    uint32_t m_track_id;
};

}  // namespace pylibheif
