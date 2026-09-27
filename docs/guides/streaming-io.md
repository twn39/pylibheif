# Streaming & Zero-Copy I/O

`pylibheif` is designed for high-concurrency microservices, cloud storage ingestion (e.g. AWS S3, Cloudflare R2), and real-time streaming pipelines where memory allocation overhead must be eliminated.

---

## Streaming Reads (`read_from_stream`)

Instead of buffering an entire multi-megabyte image in memory or saving temporary files to disk, `pylibheif` reads directly from Python file-like objects (e.g., `io.BytesIO`, open file descriptors, `urllib3` streams):

```python
import io
import pylibheif

# Any file-like object with .read() and .seek()
stream = io.BytesIO(downloaded_image_bytes)

ctx = pylibheif.HeifContext()
ctx.read_from_stream(stream)

handle = ctx.get_primary_image_handle()
print(f"Decoded stream image: {handle.width}x{handle.height}")
```

### High-Throughput Read-Ahead Caching
Behind the scenes, `src/io_bridge.hpp` implements `PyStreamReader`, which provides:
- Adaptive chunked read-ahead caching (>300,000 ops/sec).
- Low GIL lock contention during repeated seek/read operations.

---

## Zero-Copy Memory Export (`write_to_memoryview`)

Standard image libraries typically create an intermediate C++ vector, copy it into a Python `bytes` object, and trigger memory doubling. 

`pylibheif` provides `write_to_memoryview()`, which exports encoded data directly as a Python `memoryview` backed by an RAII C++ memory capsule:

```python
import pylibheif

ctx = pylibheif.HeifContext()
# (Populate context and encode image...)

# Returns memoryview backed by a C++ RAII capsule - 0 copies!
view = ctx.write_to_memoryview()

print(f"Encoded size: {len(view)} bytes")

# Write directly to network socket or file without copying
with open("output.heic", "wb") as f:
    f.write(view)
```

The underlying memory remains valid even if `ctx` is destroyed, because the capsule independently manages the native buffer lifetime.

---

## Streaming Writes (`write_to_stream`)

You can also stream the output binary incrementally into any Python writable stream:

```python
import io
import pylibheif

out_stream = io.BytesIO()

ctx = pylibheif.HeifContext()
# (Encode image into context...)

# Stream output directly into out_stream
ctx.write_to_stream(out_stream)
out_bytes = out_stream.getvalue()
```
