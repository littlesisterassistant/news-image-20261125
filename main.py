# Copy the front-page image to the output directory.
#
# Standard library only. Reads entry.png from beside this file and writes
# it, byte for byte, to MAKEFUN_OUTPUT_DIR (default /output) as entry.png,
# then reads the copy back and checks it matches (sha256) and that the
# image dimensions are 1024 by 1024 at most. Works for both PNG and JPEG
# files: the format is told apart by the first bytes, and the dimensions
# come from the PNG IHDR chunk or from a JPEG SOF marker scan.

import hashlib
import os
import shutil
import struct
import sys

MAX_BYTES = 1048576
MAX_SIDE = 1024


def fail(message):
    sys.stderr.write("error: " + message + "\n")
    sys.exit(1)


def png_dimensions(data):
    if len(data) < 24:
        fail("PNG file is too short to hold an IHDR chunk")
    if data[12:16] != b"IHDR":
        fail("PNG file has no IHDR chunk where one was expected")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def jpeg_dimensions(data):
    # Walk the JPEG markers until a start-of-frame marker gives the size.
    # SOF0 (0xC0), SOF1 (0xC1) and SOF2 (0xC2) all carry the dimensions;
    # the other SOF markers (0xC3, 0xC5-0xC7, 0xC9-0xCB, 0xCD-0xCF)
    # are accepted too. Standalone markers carry no length field.
    pos = 2
    standalone = {0x01, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7,
                  0xD8, 0xD9}
    while pos + 1 < len(data):
        if data[pos] != 0xFF:
            fail("JPEG data is not a valid marker stream at offset %d" % pos)
        marker = data[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker in standalone:
            pos += 2
            continue
        if marker == 0xDA:
            fail("JPEG scan data reached before any SOF marker")
        if pos + 4 > len(data):
            fail("JPEG file ends inside a marker segment")
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if length < 2 or pos + 2 + length > len(data):
            fail("JPEG marker segment overruns the file")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            body = data[pos + 4:pos + 2 + length]
            if len(body) < 5:
                fail("JPEG SOF segment is too short to hold dimensions")
            height, width = struct.unpack(">HH", body[1:5])
            return width, height
        pos += 2 + length
    fail("no SOF marker found in JPEG file")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, "entry.png")
    if not os.path.isfile(source):
        fail("entry.png not found beside main.py in " + here)

    try:
        with open(source, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        fail("cannot read entry.png: " + str(exc))

    if len(data) > MAX_BYTES:
        fail("entry.png is %d bytes, over the 1 MiB limit" % len(data))

    if data[:8] == b"\x89PNG\r\n\x1a\n":
        kind = "PNG"
        width, height = png_dimensions(data)
    elif data[:3] == b"\xff\xd8\xff":
        kind = "JPEG"
        width, height = jpeg_dimensions(data)
    else:
        fail("entry.png is neither a PNG nor a JPEG by its first bytes")

    if width > MAX_SIDE or height > MAX_SIDE:
        fail("image is %dx%d, over the 1024x1024 limit" % (width, height))
    if width < 1 or height < 1:
        fail("image has a zero dimension: %dx%d" % (width, height))

    # The gate wants a whole image: a JPEG must end with its EOI marker
    # and a PNG with its IEND chunk.
    if kind == "JPEG":
        if data[-2:] != b"\xff\xd9":
            fail("JPEG file does not end with the EOI marker")
    else:
        if data[-12:] != b"\x00\x00\x00\x00IEND\xaeB`\x82":
            fail("PNG file does not end with the IEND chunk")

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        fail("cannot create output dir " + out_dir + ": " + str(exc))

    dest = os.path.join(out_dir, "entry.png")
    try:
        shutil.copyfile(source, dest)
    except OSError as exc:
        fail("cannot write " + dest + ": " + str(exc))

    try:
        with open(dest, "rb") as handle:
            written = handle.read()
    except OSError as exc:
        fail("cannot read back " + dest + ": " + str(exc))

    if written != data:
        fail("read-back check failed: written bytes differ from entry.png")
    if hashlib.sha256(written).hexdigest() != hashlib.sha256(data).hexdigest():
        fail("read-back check failed: sha256 mismatch on entry.png")

    print("wrote entry.png (%s %dx%d, %d bytes, sha256 %s)"
          % (kind, width, height, len(data),
             hashlib.sha256(data).hexdigest()))


if __name__ == "__main__":
    main()
