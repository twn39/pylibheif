import pylibheif
import numpy as np

def test():
    # Write a dummy image
    img = pylibheif.HeifImage(64, 64, pylibheif.HeifColorspace.RGB, pylibheif.HeifChroma.InterleavedRGB)
    img.add_plane(pylibheif.HeifChannel.Interleaved, 64, 64, 8)
    arr = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    arr[:] = 127
    
    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    encoder.set_lossy_quality(50)
    handle = encoder.encode_image(ctx, img)
    
    print("Handle added. With width:", handle.width)
    del ctx
    print("Ctx deleted")
    try:
        print("Handle width:", handle.width)
    except Exception as e:
        print("Error:", e)

    print("Success")

if __name__ == '__main__':
    test()
