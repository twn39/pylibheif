import pylibheif
import numpy as np


def create_test_image(width=1280, height=720):
    """Create a synthetic image"""
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xv, yv = np.meshgrid(x, y)

    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :, 0] = (xv * 255).astype(np.uint8)
    img[:, :, 1] = (yv * 255).astype(np.uint8)
    # Add some complex texture/noise to make compression visible
    noise = np.random.normal(0, 20, (height, width)).astype(np.uint8)
    img[:, :, 2] = 100 + noise

    heif_img = pylibheif.HeifImage(
        width, height, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
    )
    heif_img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    plane = heif_img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    np_plane = np.asarray(plane)
    np_plane[:] = img

    return heif_img, img


def calculate_psnr(original, decoded):
    mse = np.mean((original.astype(float) - decoded.astype(float)) ** 2)
    if mse == 0:
        return 100.0
    max_pixel = 255.0
    return 20 * np.log10(max_pixel / np.sqrt(mse))


def get_psnr_for_encoder(desc, quality, image, original_np, params=None):
    try:
        ctx = pylibheif.HeifContext()
        enc = pylibheif.HeifEncoder(desc)
        enc.set_lossy_quality(quality)
        if params:
            for k, v in params.items():
                enc.set_parameter(k, v)

        enc.encode_image(ctx, image)

        encoded_data = ctx.write_to_bytes()

        decode_ctx = pylibheif.HeifContext()
        decode_ctx.read_from_memory(encoded_data)
        handle = decode_ctx.get_primary_image_handle()
        decoded_img = handle.decode(
            pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB
        )
        decoded_plane = np.asarray(
            decoded_img.get_plane(pylibheif.HeifChannel.Interleaved, False)
        )

        return calculate_psnr(original_np, decoded_plane)
    except Exception:
        return 0


def main():
    print("Generating test image (720p)...")
    heif_img, original_np = create_test_image()

    descriptors = pylibheif.get_encoder_descriptors()

    # 1. Establish Baseline: x265 Q80
    x265_desc = next(d for d in descriptors if "x265" in d.id_name)
    baseline_q = 80
    print(f"Calculating Baseline: x265 Quality={baseline_q} (Preset: medium)...")
    target_psnr = get_psnr_for_encoder(x265_desc, baseline_q, heif_img, original_np)
    print(f"Target PSNR: {target_psnr:.2f} dB")
    print("-" * 60)
    print(f"{'Encoder':<12} | {'Matching Q':<10} | {'Actual PSNR':<12} | {'Delta':<10}")
    print("-" * 60)

    encoders = [
        ("Kvazaar", "kvazaar", {}),
        ("AOM AV1", "aom", {"speed": "6"}),
        ("SVT AV1", "svt", {"speed": "6", "tune": "psnr"}),
    ]

    for name, id_filter, params in encoders:
        desc = next((d for d in descriptors if id_filter in d.id_name), None)
        if not desc:
            continue

        # Binary search / Scan to find closest Quality
        best_q = 0
        min_diff = 100.0
        best_psnr = 0

        # Scan probable range 60-100
        for q in range(60, 101, 2):  # Step 2
            psnr = get_psnr_for_encoder(desc, q, heif_img, original_np, params)
            diff = abs(psnr - target_psnr)
            if diff < min_diff:
                min_diff = diff
                best_q = q
                best_psnr = psnr

        print(
            f"{name:<12} | {best_q:<10} | {best_psnr:<12.2f} | {best_psnr - target_psnr:+.2f}"
        )


if __name__ == "__main__":
    main()
