#include "track.hpp"

#include <nanobind/nanobind.h>

#include "context.hpp"
#include "encoder.hpp"
#include "image.hpp"

namespace pylibheif {

HeifTrack::HeifTrack(heif_track* track, std::shared_ptr<ContextState> state, uint32_t track_id)
    : m_track(track, &heif_track_release), m_state(std::move(state)), m_track_id(track_id) {}

uint32_t HeifTrack::id() const {
    if (!m_track) return 0;
    return heif_track_get_id(m_track.get());
}

heif_track_type HeifTrack::track_type() const {
    if (!m_track) return 0;
    return heif_track_get_track_handler_type(m_track.get());
}

uint32_t HeifTrack::timescale() const {
    if (!m_track) return 0;
    return heif_track_get_timescale(m_track.get());
}

uint32_t HeifTrack::number_of_repetitions() const {
    if (!m_track) return 1;
    return heif_track_get_number_of_repetitions(m_track.get());
}

std::pair<uint16_t, uint16_t> HeifTrack::resolution() const {
    if (!m_track) return {0, 0};
    uint16_t w = 0, h = 0;
    heif_error err = heif_track_get_image_resolution(m_track.get(), &w, &h);
    if (err.code != heif_error_Ok) {
        return {0, 0};
    }
    return {w, h};
}

bool HeifTrack::has_alpha_channel() const {
    if (!m_track) return false;
    return heif_track_has_alpha_channel(m_track.get()) != 0;
}

void HeifTrack::encode_sequence_image(const HeifImage& image, HeifEncoder& encoder,
                                      bool save_alpha) {
    if (!m_track) {
        throw std::runtime_error("Invalid or closed track.");
    }
    heif_sequence_encoding_options* seq_opts = heif_sequence_encoding_options_alloc();
    if (seq_opts) {
        seq_opts->save_alpha_channel = save_alpha ? 1 : 0;
        seq_opts->content_kind = heif_sequence_content_kind_video;
        seq_opts->keyframe_distance_max = 30;
    }
    heif_error err;
    {
        nb::gil_scoped_release release;
        err = heif_track_encode_sequence_image(m_track.get(), image.get(), encoder.get(), seq_opts);
    }
    if (seq_opts) {
        heif_sequence_encoding_options_release(seq_opts);
    }
    check_error(err);
}

void HeifTrack::encode_end_of_sequence(HeifEncoder& encoder) {
    if (!m_track) {
        throw std::runtime_error("Invalid or closed track.");
    }
    heif_error err;
    {
        nb::gil_scoped_release release;
        err = heif_track_encode_end_of_sequence(m_track.get(), encoder.get());
    }
    check_error(err);
}

std::optional<HeifImage> HeifTrack::decode_next_image(heif_colorspace colorspace,
                                                      heif_chroma chroma,
                                                      const HeifDecodingOptions* options) {
    if (!m_track) {
        throw std::runtime_error("Invalid or closed track.");
    }

    if (chroma == heif_chroma_undefined) {
        chroma = has_alpha_channel() ? heif_chroma_interleaved_RGBA : heif_chroma_interleaved_RGB;
    }

    // Default to ignore_sequence_editlist = 1 to prevent infinite loop on looping animations
    HeifDecodingOptions default_opts;
    const heif_decoding_options* raw_opts = nullptr;
    if (options && options->get()) {
        raw_opts = options->get();
    } else {
        default_opts.get()->ignore_sequence_editlist = 1;
        raw_opts = default_opts.get();
    }

    heif_image* img = nullptr;
    heif_error err;
    {
        nb::gil_scoped_release release;
        err = heif_track_decode_next_image(m_track.get(), &img, colorspace, chroma, raw_opts);
    }

    if (err.code == heif_error_End_of_sequence) {
        return std::nullopt;
    }
    check_error(err);
    if (!img) {
        return std::nullopt;
    }
    return HeifImage(img);
}

void HeifTrack::rewind() {
    if (!m_state || !m_state->ctx) {
        throw std::runtime_error("Context has been closed.");
    }
    heif_track* t = heif_context_get_track(m_state->ctx.get(), m_track_id);
    if (!t) {
        throw std::runtime_error("Failed to rewind track.");
    }
    m_track.reset(t);
}

}  // namespace pylibheif
