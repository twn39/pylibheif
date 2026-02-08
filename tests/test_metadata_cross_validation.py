import pytest
import pylibheif
import numpy as np
import os
import io
from PIL import Image
import pillow_heif

def create_dummy_image(width=64, height=64):
    img = pylibheif.HeifImage(width, height, 
                              pylibheif.HeifColorspace.RGB,
                              pylibheif.HeifChroma.InterleavedRGB)
    img.add_plane(pylibheif.HeifChannel.Interleaved, width, height, 8)
    plane = img.get_plane(pylibheif.HeifChannel.Interleaved, True)
    np.asarray(plane)[:] = 128
    return img

def test_metadata_cross_validation_with_pillow_heif(tmp_path):
    """
    Cross-validate metadata written by pylibheif using the mature pillow-heif library.
    """
    pillow_heif.register_heif_opener()
    
    # 1. Prepare Image and Metadata
    img = create_dummy_image()

    # Create a real EXIF structure using Pillow
    temp_img = Image.new("RGB", (1, 1))
    exif = temp_img.getexif()
    exif[0x0131] = "pylibheif-cross-val"  # Software tag
    exif[0x010F] = "Gemini-CLI"          # Make tag
    
    # Export EXIF to bytes (TIFF structure)
    exif_payload = exif.tobytes()
    # libheif / pylibheif expects 4-byte offset + 'Exif\0\0' + TIFF data
    exif_data = b"\x00\x00\x00\x00" + b"Exif\x00\x00" + exif_payload

    xmp_data = b'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:description>Cross-validation test</dc:description>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''

    # 2. Write with pylibheif
    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    handle = encoder.encode_image(ctx, img)

    ctx.add_exif_metadata(handle, exif_data)
    ctx.add_xmp_metadata(handle, xmp_data)

    output_path = tmp_path / "cross_val.heic"
    ctx.write_to_file(str(output_path))

    # 3. Read back with pillow-heif
    heif_file = pillow_heif.read_heif(str(output_path))
    returned_exif = heif_file.info["exif"]
    
    # Verify specific tags are present in the returned bytes
    assert b"pylibheif-cross-val" in returned_exif
    assert b"Gemini-CLI" in returned_exif
    
    # Verify with Pillow's EXIF parser
    # We need to wrap the bytes back into a Pillow Image to use its parser easily
    val_img = Image.open(output_path)
    parsed_exif = val_img.getexif()
    assert parsed_exif[0x0131] == "pylibheif-cross-val"
    assert parsed_exif[0x010F] == "Gemini-CLI"

def test_metadata_cross_validation_with_pil(tmp_path):
    """
    Cross-validate using PIL (Pillow) directly with pillow-heif registration.
    """
    pillow_heif.register_heif_opener()

    img = create_dummy_image()
    temp_img = Image.new("RGB", (1, 1))
    exif = temp_img.getexif()
    exif[0x0131] = "PIL-Direct-Val"
    exif_payload = exif.tobytes()
    exif_data = b"\x00\x00\x00\x00" + b"Exif\x00\x00" + exif_payload

    ctx = pylibheif.HeifContext()
    encoder = pylibheif.HeifEncoder(pylibheif.HeifCompressionFormat.HEVC)
    handle = encoder.encode_image(ctx, img)
    ctx.add_exif_metadata(handle, exif_data)

    output_path = tmp_path / "pil_val.heic"
    ctx.write_to_file(str(output_path))

    # Read with Pillow
    with Image.open(output_path) as pil_img:
        parsed_exif = pil_img.getexif()
        assert parsed_exif[0x0131] == "PIL-Direct-Val"

def test_pylibheif_read_metadata_cross_validation(tmp_path):
    """
    Cross-validate reading metadata with pylibheif from a file created by pillow-heif.
    """
    # 1. Create a HEIC file using pillow-heif with specific metadata
    output_path = tmp_path / "read_val.heic"
    pil_img = Image.new("RGB", (64, 64), color="red")
    
    exif = pil_img.getexif()
    exif[0x0131] = "Created-By-Pillow-Heif"
    exif[0x0110] = "Test-Model-X"
    
    xmp_payload = b"<x:xmpmeta>Read Cross-validation</x:xmpmeta>"
    
    # Save using pillow-heif
    pil_img.save(output_path, format="HEIF", exif=exif, xmp=xmp_payload)

    # 2. Read back with pylibheif
    ctx = pylibheif.HeifContext()
    ctx.read_from_file(str(output_path))
    handle = ctx.get_primary_image_handle()

    # Check EXIF
    exif_ids = handle.get_metadata_block_ids("Exif")
    assert len(exif_ids) > 0
    exif_data = handle.get_metadata_block(exif_ids[0])
    
    # Check if our specific strings exist in the raw block returned by libheif
    assert b"Created-By-Pillow-Heif" in exif_data
    assert b"Test-Model-X" in exif_data
    
    # Check XMP
    xmp_ids = handle.get_metadata_block_ids("XMP")
    if not xmp_ids:
        # Some versions/encoders might label it as "mime"
        xmp_ids = handle.get_metadata_block_ids("")
    
    found_xmp = False
    for mid in xmp_ids:
        data = handle.get_metadata_block(mid)
        if b"Read Cross-validation" in data:
            found_xmp = True
            break
    
    assert found_xmp, "pylibheif should be able to read XMP written by pillow-heif"
