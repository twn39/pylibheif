#pragma once

#include <libheif/heif.h>
#include <nanobind/nanobind.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

namespace pylibheif {

namespace nb = nanobind;

class PyStreamReader {
   public:
    explicit PyStreamReader(nb::object stream, size_t buffer_size = 65536)
        : m_stream(stream), m_buffer(buffer_size) {
        nb::gil_scoped_acquire acquire;
        try {
            m_current_pos = nb::cast<int64_t>(m_stream.attr("tell")());
        } catch (...) {
            m_current_pos = 0;
        }

        try {
            // Check if stream supports seek to end to cache file size
            m_stream.attr("seek")(0, 2);  // os.SEEK_END = 2
            m_file_size = nb::cast<int64_t>(m_stream.attr("tell")());
            m_stream.attr("seek")(m_current_pos, 0);  // os.SEEK_SET = 0
        } catch (...) {
            // Seek to end not supported (e.g. non-seekable or streaming network socket)
            m_file_size = -1;
            try {
                m_stream.attr("seek")(m_current_pos, 0);
            } catch (...) {
            }
        }
    }

    int64_t get_position() const { return m_current_pos; }

    int seek(int64_t position) {
        if (position == m_current_pos) {
            return 0;
        }
        // If target position is inside our current cached buffer window, just update logical
        // pointer
        if (position >= m_buffer_pos &&
            position < m_buffer_pos + static_cast<int64_t>(m_buffer_valid_len)) {
            m_current_pos = position;
            return 0;
        }

        // Seeking outside cached buffer window: logical seek
        m_current_pos = position;
        return 0;
    }

    int read(void* out_data, size_t size) {
        if (size == 0) {
            return 0;
        }

        uint8_t* out_ptr = static_cast<uint8_t*>(out_data);
        size_t remaining_to_read = size;

        while (remaining_to_read > 0) {
            // 1. Check if current position falls within cached buffer window
            if (m_current_pos >= m_buffer_pos &&
                m_current_pos < m_buffer_pos + static_cast<int64_t>(m_buffer_valid_len)) {
                size_t offset_in_buf = static_cast<size_t>(m_current_pos - m_buffer_pos);
                size_t avail = m_buffer_valid_len - offset_in_buf;
                size_t chunk = std::min(remaining_to_read, avail);

                std::memcpy(out_ptr, m_buffer.data() + offset_in_buf, chunk);
                m_current_pos += chunk;
                out_ptr += chunk;
                remaining_to_read -= chunk;
                continue;
            }

            // 2. Buffer miss: must fetch data from Python stream under GIL
            nb::gil_scoped_acquire acquire;
            try {
                // First, ensure underlying python stream seek matches m_current_pos
                m_stream.attr("seek")(m_current_pos, 0);

                // If request is larger than our buffer size, read directly into output
                if (remaining_to_read >= m_buffer.size()) {
                    nb::object py_chunk = m_stream.attr("read")(remaining_to_read);
                    Py_buffer view;
                    if (PyObject_GetBuffer(py_chunk.ptr(), &view, PyBUF_SIMPLE) != 0) {
                        return -1;
                    }
                    size_t got = static_cast<size_t>(view.len);
                    if (got == 0) {
                        PyBuffer_Release(&view);
                        return -1;  // EOF
                    }
                    std::memcpy(out_ptr, view.buf, got);
                    PyBuffer_Release(&view);

                    m_current_pos += got;
                    out_ptr += got;
                    remaining_to_read -= got;
                    m_buffer_valid_len = 0;  // invalidated buffer
                    if (got < remaining_to_read) {
                        // Premature EOF
                        return -1;
                    }
                } else {
                    // Refill buffer with buffer_size
                    nb::object py_chunk = m_stream.attr("read")(m_buffer.size());
                    Py_buffer view;
                    if (PyObject_GetBuffer(py_chunk.ptr(), &view, PyBUF_SIMPLE) != 0) {
                        return -1;
                    }
                    size_t got = static_cast<size_t>(view.len);
                    if (got == 0) {
                        PyBuffer_Release(&view);
                        return -1;  // EOF
                    }
                    std::memcpy(m_buffer.data(), view.buf, got);
                    PyBuffer_Release(&view);

                    m_buffer_pos = m_current_pos;
                    m_buffer_valid_len = got;

                    // Copy portion needed
                    size_t chunk = std::min(remaining_to_read, got);
                    std::memcpy(out_ptr, m_buffer.data(), chunk);
                    m_current_pos += chunk;
                    out_ptr += chunk;
                    remaining_to_read -= chunk;
                }
            } catch (...) {
                return -1;  // Python exception mapped to reader error
            }
        }

        return 0;
    }

    heif_reader_grow_status wait_for_file_size(int64_t target_size) {
        if (m_file_size >= 0) {
            if (target_size <= m_file_size) {
                return heif_reader_grow_status_size_reached;
            } else {
                return heif_reader_grow_status_size_beyond_eof;
            }
        }

        // Unknown file size, query under GIL
        nb::gil_scoped_acquire acquire;
        try {
            int64_t current = nb::cast<int64_t>(m_stream.attr("tell")());
            m_stream.attr("seek")(0, 2);
            m_file_size = nb::cast<int64_t>(m_stream.attr("tell")());
            m_stream.attr("seek")(current, 0);

            if (target_size <= m_file_size) {
                return heif_reader_grow_status_size_reached;
            } else {
                return heif_reader_grow_status_size_beyond_eof;
            }
        } catch (...) {
            return heif_reader_grow_status_size_reached;
        }
    }

    // Static trampoline functions for heif_reader
    static int64_t trampoline_get_position(void* userdata) {
        return static_cast<PyStreamReader*>(userdata)->get_position();
    }

    static int trampoline_read(void* data, size_t size, void* userdata) {
        return static_cast<PyStreamReader*>(userdata)->read(data, size);
    }

    static int trampoline_seek(int64_t position, void* userdata) {
        return static_cast<PyStreamReader*>(userdata)->seek(position);
    }

    static heif_reader_grow_status trampoline_wait_for_file_size(int64_t target_size,
                                                                 void* userdata) {
        return static_cast<PyStreamReader*>(userdata)->wait_for_file_size(target_size);
    }

   private:
    nb::object m_stream;
    std::vector<uint8_t> m_buffer;
    int64_t m_buffer_pos = 0;
    size_t m_buffer_valid_len = 0;
    int64_t m_current_pos = 0;
    int64_t m_file_size = -1;
};

class PyStreamWriter {
   public:
    explicit PyStreamWriter(nb::object stream) : m_stream(stream) {}

    heif_error write(const void* data, size_t size) {
        nb::gil_scoped_acquire acquire;
        try {
            nb::bytes chunk(static_cast<const char*>(data), size);
            m_stream.attr("write")(chunk);
            return {heif_error_Ok, heif_suberror_Unspecified, "Success"};
        } catch (const std::exception& ex) {
            return {heif_error_Encoding_error, heif_suberror_Cannot_write_output_data, ex.what()};
        } catch (...) {
            return {heif_error_Encoding_error, heif_suberror_Cannot_write_output_data,
                    "Unknown error writing to Python stream"};
        }
    }

    static heif_error trampoline_write(heif_context* /*ctx*/, const void* data, size_t size,
                                       void* userdata) {
        return static_cast<PyStreamWriter*>(userdata)->write(data, size);
    }

   private:
    nb::object m_stream;
};

}  // namespace pylibheif
