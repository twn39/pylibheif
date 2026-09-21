#pragma once

#include <libheif/heif.h>
#include <nanobind/nanobind.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <exception>
#include <memory>
#include <string>
#include <vector>

namespace pylibheif {

namespace nb = nanobind;

class PyStreamReader {
   public:
    enum class ReadStrategy { AutoDetect, UseReadinto, FallbackRead };

    explicit PyStreamReader(nb::object stream, size_t buffer_size = 65536)
        : m_stream(stream), m_buffer(buffer_size) {
        nb::gil_scoped_acquire acquire;
        if (nb::hasattr(m_stream, "read")) {
            m_read_method = m_stream.attr("read");
        }
        if (nb::hasattr(m_stream, "seek")) {
            m_seek_method = m_stream.attr("seek");
        }
        if (nb::hasattr(m_stream, "tell")) {
            m_tell_method = m_stream.attr("tell");
        }
        if (nb::hasattr(m_stream, "readinto")) {
            m_readinto_method = m_stream.attr("readinto");
        }

        try {
            if (m_tell_method.is_valid()) {
                m_current_pos = nb::cast<int64_t>(m_tell_method());
            } else {
                m_current_pos = 0;
            }
        } catch (...) {
            m_current_pos = 0;
        }
        m_stream_pos = m_current_pos;

        try {
            // Check if stream supports seek to end to cache file size
            if (m_seek_method.is_valid() && m_tell_method.is_valid()) {
                m_seek_method(0, 2);  // os.SEEK_END = 2
                m_file_size = nb::cast<int64_t>(m_tell_method());
                m_seek_method(m_current_pos, 0);  // os.SEEK_SET = 0
                m_stream_pos = m_current_pos;

                // Adaptive buffer sizing: for large streams (>10MB), dynamically size up buffer
                // to 128KB (or 256KB for >50MB) to reduce Python call transitions by up to 75%
                if (m_file_size > 50 * 1024 * 1024 && buffer_size == 65536) {
                    m_buffer.resize(262144);
                } else if (m_file_size > 10 * 1024 * 1024 && buffer_size == 65536) {
                    m_buffer.resize(131072);
                }
            }
        } catch (...) {
            // Seek to end not supported (e.g. non-seekable or streaming network socket)
            m_file_size = -1;
            try {
                if (m_seek_method.is_valid()) {
                    m_seek_method(m_current_pos, 0);
                    m_stream_pos = m_current_pos;
                }
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
                // Seek only if current position differs from underlying stream position (redundant
                // seek elimination)
                if (m_stream_pos != m_current_pos) {
                    if (m_seek_method.is_valid()) {
                        m_seek_method(m_current_pos, 0);
                    } else {
                        m_stream.attr("seek")(m_current_pos, 0);
                    }
                    m_stream_pos = m_current_pos;
                }

                // If request is larger than our buffer size, read directly into output
                if (remaining_to_read >= m_buffer.size()) {
                    size_t got = 0;
                    if (m_read_strategy != ReadStrategy::FallbackRead) {
                        try {
                            PyObject* mv_obj = PyMemoryView_FromMemory(
                                reinterpret_cast<char*>(out_ptr), remaining_to_read, PyBUF_WRITE);
                            if (mv_obj) {
                                nb::object mv = nb::steal(mv_obj);
                                nb::object ret = m_readinto_method.is_valid()
                                                     ? m_readinto_method(mv)
                                                     : m_stream.attr("readinto")(mv);
                                if (!ret.is_none()) {
                                    got = nb::cast<size_t>(ret);
                                    m_read_strategy = ReadStrategy::UseReadinto;
                                }
                            }
                        } catch (const nb::python_error&) {
                            if (m_read_strategy == ReadStrategy::AutoDetect) {
                                m_read_strategy = ReadStrategy::FallbackRead;
                            } else {
                                throw;
                            }
                        }
                    }

                    if (m_read_strategy == ReadStrategy::FallbackRead) {
                        nb::object py_chunk = m_read_method.is_valid()
                                                  ? m_read_method(remaining_to_read)
                                                  : m_stream.attr("read")(remaining_to_read);
                        Py_buffer view;
                        if (PyObject_GetBuffer(py_chunk.ptr(), &view, PyBUF_SIMPLE) != 0) {
                            return -1;
                        }
                        got = static_cast<size_t>(view.len);
                        if (got > 0) {
                            std::memcpy(out_ptr, view.buf, got);
                        }
                        PyBuffer_Release(&view);
                    }

                    if (got == 0) {
                        return -1;  // EOF
                    }

                    m_stream_pos += got;
                    m_current_pos += got;
                    out_ptr += got;
                    remaining_to_read -= got;
                    m_buffer_valid_len = 0;  // invalidated buffer
                    if (remaining_to_read > 0) {
                        // Premature EOF
                        return -1;
                    }
                } else {
                    // Refill buffer with buffer_size
                    size_t got = 0;
                    if (m_read_strategy != ReadStrategy::FallbackRead) {
                        try {
                            // Short-read packing loop: try to fill m_buffer as much as possible
                            while (got < m_buffer.size()) {
                                PyObject* mv_obj = PyMemoryView_FromMemory(
                                    reinterpret_cast<char*>(m_buffer.data() + got),
                                    m_buffer.size() - got, PyBUF_WRITE);
                                if (!mv_obj) break;
                                nb::object mv = nb::steal(mv_obj);
                                nb::object ret = m_readinto_method.is_valid()
                                                     ? m_readinto_method(mv)
                                                     : m_stream.attr("readinto")(mv);
                                if (ret.is_none()) break;
                                size_t n = nb::cast<size_t>(ret);
                                if (n == 0) break;  // EOF reached
                                got += n;
                                m_read_strategy = ReadStrategy::UseReadinto;
                            }
                        } catch (const nb::python_error&) {
                            if (m_read_strategy == ReadStrategy::AutoDetect) {
                                m_read_strategy = ReadStrategy::FallbackRead;
                            } else {
                                throw;
                            }
                        }
                    }

                    if (m_read_strategy == ReadStrategy::FallbackRead) {
                        nb::object py_chunk = m_read_method.is_valid()
                                                  ? m_read_method(m_buffer.size())
                                                  : m_stream.attr("read")(m_buffer.size());
                        Py_buffer view;
                        if (PyObject_GetBuffer(py_chunk.ptr(), &view, PyBUF_SIMPLE) != 0) {
                            return -1;
                        }
                        got = static_cast<size_t>(view.len);
                        if (got > 0) {
                            std::memcpy(m_buffer.data(), view.buf, got);
                        }
                        PyBuffer_Release(&view);
                    }

                    if (got == 0) {
                        return -1;  // EOF
                    }

                    m_stream_pos += got;
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
            m_stream_pos = current;

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
    nb::object m_read_method;
    nb::object m_seek_method;
    nb::object m_tell_method;
    nb::object m_readinto_method;
    std::vector<uint8_t> m_buffer;
    int64_t m_buffer_pos = 0;
    size_t m_buffer_valid_len = 0;
    int64_t m_current_pos = 0;
    int64_t m_stream_pos = 0;
    int64_t m_file_size = -1;
    ReadStrategy m_read_strategy = ReadStrategy::AutoDetect;
};

class PyStreamWriter {
   public:
    explicit PyStreamWriter(nb::object stream, size_t buffer_size = 65536)
        : m_stream(stream), m_buffer(buffer_size), m_buffered_len(0) {
        nb::gil_scoped_acquire acquire;
        if (nb::hasattr(m_stream, "write")) {
            m_write_method = m_stream.attr("write");
        }
    }

    ~PyStreamWriter() {
        try {
            flush();
        } catch (...) {
        }
    }

    heif_error flush() {
        if (m_buffered_len == 0) {
            return {heif_error_Ok, heif_suberror_Unspecified, "Success"};
        }
        nb::gil_scoped_acquire acquire;
        try {
            nb::bytes chunk(reinterpret_cast<const char*>(m_buffer.data()), m_buffered_len);
            m_buffered_len = 0;
            if (m_write_method.is_valid()) {
                m_write_method(chunk);
            } else {
                m_stream.attr("write")(chunk);
            }
            return {heif_error_Ok, heif_suberror_Unspecified, "Success"};
        } catch (const std::exception& ex) {
            m_buffered_len = 0;
            m_captured_exception = std::current_exception();
            return {heif_error_Encoding_error, heif_suberror_Cannot_write_output_data, ex.what()};
        } catch (...) {
            m_buffered_len = 0;
            m_captured_exception = std::current_exception();
            return {heif_error_Encoding_error, heif_suberror_Cannot_write_output_data,
                    "Unknown error writing to Python stream"};
        }
    }

    heif_error write(const void* data, size_t size) {
        if (size == 0) {
            return {heif_error_Ok, heif_suberror_Unspecified, "Success"};
        }

        const uint8_t* src = static_cast<const uint8_t*>(data);

        // Case 1: Oversized chunk (>= buffer size)
        // Flush any buffered data first, then write directly to python stream under GIL
        if (size >= m_buffer.size()) {
            heif_error err = flush();
            if (err.code != heif_error_Ok) {
                return err;
            }
            nb::gil_scoped_acquire acquire;
            try {
                nb::bytes chunk(reinterpret_cast<const char*>(src), size);
                if (m_write_method.is_valid()) {
                    m_write_method(chunk);
                } else {
                    m_stream.attr("write")(chunk);
                }
                return {heif_error_Ok, heif_suberror_Unspecified, "Success"};
            } catch (const std::exception& ex) {
                m_captured_exception = std::current_exception();
                return {heif_error_Encoding_error, heif_suberror_Cannot_write_output_data,
                        ex.what()};
            } catch (...) {
                m_captured_exception = std::current_exception();
                return {heif_error_Encoding_error, heif_suberror_Cannot_write_output_data,
                        "Unknown error writing to Python stream"};
            }
        }

        // Case 2: Chunk fits in remaining buffer space without flushing (zero GIL!)
        size_t avail = m_buffer.size() - m_buffered_len;
        if (size <= avail) {
            std::memcpy(m_buffer.data() + m_buffered_len, src, size);
            m_buffered_len += size;
            return {heif_error_Ok, heif_suberror_Unspecified, "Success"};
        }

        // Case 3: Chunk doesn't fit in remaining space -> fill buffer, flush, then buffer remainder
        std::memcpy(m_buffer.data() + m_buffered_len, src, avail);
        m_buffered_len = m_buffer.size();
        heif_error err = flush();
        if (err.code != heif_error_Ok) {
            return err;
        }

        size_t remainder = size - avail;
        if (remainder > 0) {
            std::memcpy(m_buffer.data(), src + avail, remainder);
            m_buffered_len = remainder;
        }

        return {heif_error_Ok, heif_suberror_Unspecified, "Success"};
    }

    void rethrow_if_exception() {
        if (m_captured_exception) {
            std::rethrow_exception(m_captured_exception);
        }
    }

    static heif_error trampoline_write(heif_context* /*ctx*/, const void* data, size_t size,
                                       void* userdata) {
        return static_cast<PyStreamWriter*>(userdata)->write(data, size);
    }

   private:
    nb::object m_stream;
    nb::object m_write_method;
    std::vector<uint8_t> m_buffer;
    size_t m_buffered_len = 0;
    std::exception_ptr m_captured_exception;
};

}  // namespace pylibheif
