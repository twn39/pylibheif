# Ultra-Fast Batch Conversion with Async Coroutines

Converting thousands of high-resolution images can easily saturate system memory or lock up the Python GIL if using naive multi-processing or unconstrained thread pools.

`pylibheif` includes native asynchronous abstractions (`AsyncHeifContext`, `AsyncHeifImageHandle`) and dynamic thread budget management (`ConcurrencyBudget`) that enable high throughput while keeping CPU and RAM within predictable limits.

This tutorial walks through building a production-ready batch converter script with Rich terminal progress rendering.

---

## Complete Async Batch Converter Script

```python
import asyncio
from pathlib import Path
from typing import List
import pylibheif
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

async def convert_image(
    input_path: Path,
    output_path: Path,
    codec: pylibheif.HeifCompressionFormat,
    preset: str = "fast",
    quality: int = 80,
    semaphore: asyncio.Semaphore = None,
    progress: Progress = None,
    task_id = None
):
    """Asynchronously decodes an input image and encodes to the target format."""
    async with semaphore:
        try:
            # 1. Open context asynchronously
            ctx = pylibheif.AsyncHeifContext()
            await ctx.read_from_file(str(input_path))

            # 2. Get handle and decode
            handle = await ctx.get_primary_image_handle()
            image = await handle.decode(
                pylibheif.HeifColorspace.RGB,
                pylibheif.HeifChroma.InterleavedRGB24
            )

            # 3. Setup target encoding context
            out_ctx = pylibheif.AsyncHeifContext()
            encoder = pylibheif.AsyncHeifEncoder(codec)
            await encoder.apply_preset(preset)
            encoder.quality = quality

            # Preserve embedded ICC or NCLX color profiles
            profile_type = handle.get_color_profile_type()
            if profile_type == pylibheif.HeifColorProfileType.Prof:
                icc_data = handle.get_raw_color_profile()
                out_ctx.set_color_profile_icc(icc_data)
            elif profile_type == pylibheif.HeifColorProfileType.Nclx:
                out_ctx.set_color_profile_nclx(handle.get_nclx_color_profile())

            # 4. Encode and save
            await out_ctx.encode_image(image, encoder)
            await out_ctx.write_to_file(str(output_path))

        except Exception as e:
            print(f"[Error] Failed to convert {input_path.name}: {e}")
        finally:
            if progress and task_id:
                progress.advance(task_id)

async def batch_convert_directory(
    source_dir: str,
    target_dir: str,
    output_format: str = "avif",
    quality: int = 80,
    preset: str = "fast",
    max_concurrency: int = 4
):
    src = Path(source_dir)
    dst = Path(target_dir)
    dst.mkdir(parents=True, exist_ok=True)

    # Collect source images
    extensions = ("*.heic", "*.heif", "*.jpg", "*.jpeg", "*.png")
    files: List[Path] = []
    for ext in extensions:
        files.extend(src.rglob(ext))

    if not files:
        print(f"No matching images found in {src}")
        return

    # Select target compression format
    codec = (
        pylibheif.HeifCompressionFormat.AV1 
        if output_format.lower() == "avif" 
        else pylibheif.HeifCompressionFormat.HEVC
    )

    # Use a Semaphore to prevent exceeding system memory limits
    sem = asyncio.Semaphore(max_concurrency)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(f"Converting {len(files)} images to {output_format.upper()}...", total=len(files))

        tasks = []
        for file in files:
            rel_path = file.relative_to(src)
            out_file = dst / rel_path.with_suffix(f".{output_format}")
            out_file.parent.mkdir(parents=True, exist_ok=True)

            t = convert_image(
                input_path=file,
                output_path=out_file,
                codec=codec,
                preset=preset,
                quality=quality,
                semaphore=sem,
                progress=progress,
                task_id=task
            )
            tasks.append(t)

        await asyncio.gather(*tasks)

    print(f"Successfully processed {len(files)} images into {dst}!")

if __name__ == "__main__":
    import sys
    # Example usage: python batch.py ./input_photos ./output_avif
    source = sys.argv[1] if len(sys.argv) > 1 else "./photos"
    dest = sys.argv[2] if len(sys.argv) > 2 else "./converted_avif"
    asyncio.run(batch_convert_directory(source, dest, output_format="avif", preset="fast"))
```

---

## Best Practices for Batch Jobs

1. **Preset Tuning**:
   - For real-time server ingestion, use `--preset ultrafast` or `--preset fast`.
   - For archiving and static asset preparation, use `--preset balanced` or `--preset quality`.
2. **Concurrency Limiting**:
   - Limit `asyncio.Semaphore` to $(N_{cpu} / 2)$ to allow native codec worker threads (such as `kvazaar` and `dav1d`) room to scale without thread contention.
