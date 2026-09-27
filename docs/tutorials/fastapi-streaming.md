# High-Performance Cloud API: Streaming HEIC to AVIF with FastAPI

Modern mobile devices (iPhones, modern Android smartphones) capture images in HEIC or Ultra HDR AVIF by default. When building web backends, microservices often need to convert these incoming images on-the-fly for web delivery without saving temporary files to disk and without duplicating memory.

This tutorial demonstrates how to build an asynchronous, zero-disk-I/O **FastAPI** service using `pylibheif`'s native streaming APIs (`read_from_stream` and `write_to_memoryview`).

---

## Why Native Streaming?

| Operation | Traditional Pipeline | `pylibheif` Native Stream Pipeline |
|---|---|---|
| **File I/O** | Writes temp file to `/tmp`, reads back | Direct in-memory stream read from socket/buffer |
| **Decoding** | Intermediate copies into RGB arrays | Direct planar decoding with zero memory copy |
| **Encoding Export** | Copies C++ vector -> Python `bytes` | Returns `memoryview` backed by C++ RAII capsule |
| **Disk Operations** | High SSD write wear & OS disk contention | **0 disk operations** |

---

## Complete FastAPI Service Implementation

```python
import io
import asyncio
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import Response
import pylibheif

app = FastAPI(title="pylibheif Image Converter API")

@app.post("/convert/avif")
async def convert_to_avif(
    file: UploadFile = File(...),
    quality: int = Query(80, ge=1, le=100, description="Target AVIF quality"),
    preset: str = Query("fast", regex="^(ultrafast|fast|balanced|quality)$")
):
    """
    Ingest a HEIC/JPEG file stream from an upload and return an optimized AVIF image.
    Uses in-memory streaming and zero-copy memoryview export.
    """
    if not file.filename.lower().endswith((".heic", ".heif", ".jpg", ".jpeg", ".png")):
        raise HTTPException(status_code=400, detail="Unsupported input image format.")

    # 1. Read input stream into an in-memory buffer (or spool)
    contents = await file.read()
    input_stream = io.BytesIO(contents)

    # 2. Decode HEIF container asynchronously without blocking event loop
    loop = asyncio.get_running_loop()

    def _process_image():
        # Open context directly from Python file-like stream
        ctx = pylibheif.HeifContext()
        ctx.read_from_stream(input_stream)
        
        handle = ctx.get_primary_image_handle()
        
        # Decode to planar RGB
        image = handle.decode(
            pylibheif.HeifColorspace.RGB,
            pylibheif.HeifChroma.InterleavedRGB24
        )

        # 3. Setup destination context and AVIF encoder
        out_ctx = pylibheif.HeifContext()
        encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.AV1)
        encoder.apply_preset(preset)
        encoder.quality = quality

        # Preserve color profile if present
        profile_type = handle.get_color_profile_type()
        if profile_type == pylibheif.HeifColorProfileType.Prof:
            icc_data = handle.get_raw_color_profile()
            out_ctx.set_color_profile_icc(icc_data)
        elif profile_type == pylibheif.HeifColorProfileType.Nclx:
            nclx = handle.get_nclx_color_profile()
            out_ctx.set_color_profile_nclx(nclx)

        # Encode image into out_ctx
        out_ctx.encode_image(image, encoder)

        # 4. Zero-copy export as memoryview backed by native C++ buffer
        return bytes(out_ctx.write_to_memoryview())

    # Offload heavy native encoding to worker thread pool
    avif_bytes = await loop.run_in_executor(None, _process_image)

    return Response(
        content=avif_bytes,
        media_type="image/avif",
        headers={
            "Content-Disposition": f'inline; filename="{file.filename.rsplit(".", 1)[0]}.avif"',
            "Cache-Control": "public, max-age=31536000, immutable"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Production Optimizations

### 1. Concurrency Budgeting
In multi-core server environments, internal codec threads (e.g. `dav1d`, `aom`) can contend with web worker processes. Set default threads globally on startup:

```python
@app.on_event("startup")
def setup_codecs():
    # Limit internal threads per encode task to prevent CPU oversubscription
    pylibheif.set_default_num_threads(2)
```

### 2. S3 / Cloudflare R2 Direct Streaming
When reading images directly from object storage (e.g. `boto3` or `httpx`), pass the raw response stream directly into `ctx.read_from_stream()`:

```python
import httpx

async def fetch_and_convert(image_url: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(image_url)
        stream = io.BytesIO(resp.content)

        ctx = pylibheif.HeifContext()
        ctx.read_from_stream(stream)
        # Proceed with decoding...
```
