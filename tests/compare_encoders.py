import pylibheif
import time
import numpy as np
import sys

def create_test_image(width=1920, height=1080):
    """Create a synthetic image with gradient and noise"""
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xv, yv = np.meshgrid(x, y)
    
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Gradient
    img[:, :, 0] = (xv * 255).astype(np.uint8)
    img[:, :, 1] = (yv * 255).astype(np.uint8)
    # Noise to make compression harder
    noise = np.random.randint(0, 30, (height, width), dtype=np.uint8)
    img[:, :, 2] = 128 + noise // 2
    
    heif_img = pylibheif.HeifImage(
        width, height,
        pylibheif.HeifColorspace.RGB,
        pylibheif.HeifChroma.InterleavedRGB
    )
    heif_img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    plane = heif_img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    np_plane = np.asarray(plane)
    np_plane[:] = img
    
    return heif_img, img

def calculate_psnr(original, decoded):
    """Calculate PSNR between two images"""
    mse = np.mean((original.astype(float) - decoded.astype(float)) ** 2)
    if mse == 0:
        return float('inf')
    max_pixel = 255.0
    psnr = 20 * np.log10(max_pixel / np.sqrt(mse))
    return psnr

def benchmark_encoder(name, encoder_setup_func, image, original_np):
    ctx = pylibheif.HeifContext()
    encoder = encoder_setup_func()
    
    start_time = time.perf_counter()
    encoder.encode_image(ctx, image)
    end_time = time.perf_counter()
    
    encoded_data = ctx.write_to_bytes()
    size_bytes = len(encoded_data)
    duration_ms = (end_time - start_time) * 1000
    
    # Decode to check quality
    decode_ctx = pylibheif.HeifContext()
    decode_ctx.read_from_memory(encoded_data)
    handle = decode_ctx.get_primary_image_handle()
    decoded_img = handle.decode(pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB)
    decoded_plane = np.asarray(decoded_img.get_plane(pylibheif.HeifChannel.Interleaved, False))
    
    psnr = calculate_psnr(original_np, decoded_plane)
    
    return duration_ms, size_bytes, psnr

def main():
    print("Generating test image...")
    heif_img, original_np = create_test_image(1280, 720) # 720p for speed
    
    descriptors = pylibheif.get_encoder_descriptors()
    
    encoders = [
        ("x265", pylibheif.HeifCompressionFormat.HEVC, None),
        ("Kvazaar", pylibheif.HeifCompressionFormat.HEVC, "kvazaar"),
        ("AOM AV1", pylibheif.HeifCompressionFormat.AV1, "aom"),
    ]
    
    # Qualities to test
    qualities = [50, 70, 85]
    
    print(f"{'Encoder':<12} | {'Qual':<4} | {'Time (ms)':<10} | {'Size (KB)':<10} | {'PSNR (dB)':<10}")
    print("-" * 60)
    
    for enc_name, fmt, id_filter in encoders:
        # Find descriptor
        desc = None
        if id_filter:
            desc = next((d for d in descriptors if id_filter in d.id_name), None)
            if not desc:
                print(f"{enc_name:<12} | SKIP (Not Found)")
                continue
        else:
            # Default for format (usually x265 for HEVC)
            desc = [d for d in descriptors if d.id_name == ('x265' if fmt == pylibheif.HeifCompressionFormat.HEVC else 'aom')][0]

        for q in qualities:
            def setup():
                enc = pylibheif.HeifEncoder(desc)
                enc.set_lossy_quality(q)
                if "AOM" in enc_name:
                    enc.set_parameter("speed", "6")
                return enc
            
            try:
                ms, size, psnr = benchmark_encoder(enc_name, setup, heif_img, original_np)
                print(f"{enc_name:<12} | {q:<4} | {ms:10.2f} | {size/1024:10.2f} | {psnr:10.2f}")
            except Exception as e:
                print(f"{enc_name:<12} | {q:<4} | ERROR: {e}")

if __name__ == "__main__":
    main()
