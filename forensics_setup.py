"""
forensics_setup.py
Generate all sample files for the CTF forensics module (2 lessons).
Run ONCE before class: python forensics_setup.py
Creates a 'forensics_files/' directory with all task files.

REQUIRES: Python 3 stdlib only (no external packages).
Works on Windows, macOS, Linux.
"""

import os
import struct
import zlib
import zipfile
import io
import random

random.seed(42)  # reproducible

OUT_DIR = 'forensics_files'
os.makedirs(OUT_DIR, exist_ok=True)


def save(name, data):
    """Save bytes to OUT_DIR/name."""
    path = os.path.join(OUT_DIR, name)
    with open(path, 'wb') as f:
        f.write(data)
    print(f"  created {path} ({len(data)} bytes)")


def make_minimal_png(extra_chunks=None, idat_chunks=1, appended_after_iend=b''):
    """Build a minimal valid PNG file.
    extra_chunks: list of (chunk_type_bytes, chunk_data_bytes)
    idat_chunks: number of IDAT chunks to write
    appended_after_iend: bytes to append after IEND
    """
    # PNG signature
    sig = b'\x89PNG\r\n\x1a\n'
    # IHDR: 1x1 pixel, 8-bit RGB
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)
    # IDAT: compressed pixel data (filter byte 0 + RGB pixel)
    raw = b'\x00\xff\x00\x00'  # filter=0, R=255, G=0, B=0
    compressed = zlib.compress(raw)
    idats = b''
    if idat_chunks == 1:
        idats = make_chunk(b'IDAT', compressed)
    else:
        # split compressed into idat_chunks pieces
        chunk_size = max(1, len(compressed) // idat_chunks)
        for i in range(idat_chunks):
            piece = compressed[i*chunk_size:(i+1)*chunk_size]
            if i == idat_chunks - 1:
                piece = compressed[i*chunk_size:]  # remainder
            if piece:
                idats += make_chunk(b'IDAT', piece)
    # extra chunks
    extras = b''
    if extra_chunks:
        for ctype, cdata in extra_chunks:
            extras += make_chunk(ctype, cdata)
    # IEND
    iend = make_chunk(b'IEND', b'')
    return sig + ihdr + extras + idats + iend + appended_after_iend


def make_chunk(ctype, data):
    """Build a PNG chunk: length + type + data + CRC."""
    length = struct.pack('>I', len(data))
    crc = struct.pack('>I', zlib.crc32(ctype + data) & 0xffffffff)
    return length + ctype + data + crc


def make_zip(files, password=None, comment=b''):
    """Build a ZIP file in memory.
    files: list of (name, content_bytes)
    password: bytes or None
    comment: archive comment bytes
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if comment:
            zf.comment = comment
        for name, content in files:
            if password:
                # Write encrypted entry via open() with pwd
                with zf.open(name, 'w', pwd=password) as f:
                    f.write(content)
            else:
                zf.writestr(name, content, compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


# ============================================================
# LESSON 1 - FILES ARE BYTES
# ============================================================
print("\n=== Lesson 1 files ===")

# Task 1: JPEG magic bytes
# Answer: JPEG
task1_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01' + bytes(random.randint(0,255) for _ in range(100))
save('task1.bin', task1_data)

# Task 2: strings - embedded ASCII flag
# Answer: ctf{find_me_in_strings}
flag2 = b'ctf{find_me_in_strings}'
data2 = bytes(random.randint(0,255) for _ in range(200))
# insert flag at random position
pos2 = 80
data2 = data2[:pos2] + flag2 + data2[pos2+len(flag2):]
data2 += bytes(random.randint(0,255) for _ in range(200))
save('task2.bin', data2)

# Task 3: PDF magic
# Answer: PDF
task3_data = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n' + b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n' + b'xref\n0 3\n0000000000 65535 f \n' + bytes(random.randint(0,255) for _ in range(50))
save('task3.bin', task3_data)

# Task 4: PNG with hidden flag in tEXt chunk (find via strings)
# Answer: ctf{filter_for_flag}
flag4 = b'ctf{filter_for_flag}'
text_chunk = (b'Comment\x00' + flag4)
png4 = make_minimal_png(extra_chunks=[(b'tEXt', text_chunk)])
save('task4.bin', png4)

# Task 5: PNG with appended text after IEND
# Answer: ctf{after_iend_chunk}
flag5 = b'\nSecret message: ctf{after_iend_chunk}\n'
png5 = make_minimal_png(appended_after_iend=flag5)
save('task5.bin', png5)

# Task 6: every 5th byte from byte 3 spells flag
# Answer: ctf{every_fifth_byte}
flag6 = b'ctf{every_fifth_byte}'
# bytes positions: 3, 8, 13, 18, ...  (5 apart starting at 3)
data6 = bytearray(random.randint(0,255) for _ in range(300))
for i, c in enumerate(flag6):
    pos = 3 + i*5
    if pos < len(data6):
        data6[pos] = c
save('task6.bin', bytes(data6))

# Task 7: PNG + ZIP + text concatenated
# Answer: 3 flags
# PNG with tEXt containing flag
flag7a = b'ctf{in_png_text}'
png7 = make_minimal_png(extra_chunks=[(b'tEXt', b'Secret\x00' + flag7a)])
# ZIP with flag.txt
flag7b = b'ctf{in_zip_file}'
zip7 = make_zip([('flag.txt', flag7b)])
# Plain text with flag
flag7c = b'\nFinal flag: ctf{plain_text_tail}\n'
task7_data = png7 + zip7 + flag7c
save('task7.bin', task7_data)

# Task 8: every 13th byte from byte 5, only printable 32-126
# Answer: ctf{lucky_number_13}
flag8 = b'ctf{lucky_number_13}'
data8 = bytearray(random.randint(0,255) for _ in range(500))
# make sure surrounding bytes are non-printable to enforce the rule
for i, c in enumerate(flag8):
    pos = 5 + i*13
    data8[pos] = c
    # make neighbors non-printable
    if pos > 0:
        data8[pos-1] = random.randint(128, 250)
    if pos+1 < len(data8):
        data8[pos+1] = random.randint(128, 250)
save('task8.bin', bytes(data8))


# ============================================================
# LESSON 2 - FILE STRUCTURE
# ============================================================
print("\n=== Lesson 2 files ===")

# Task 1: PNG with tEXt chunk containing flag
# Answer: ctf{png_text_chunk}
flag_l2_1 = b'ctf{png_text_chunk}'
png_l2_1 = make_minimal_png(extra_chunks=[(b'tEXt', b'Comment\x00' + flag_l2_1)])
save('png_task1.png', png_l2_1)

# Task 2: ZIP with comment containing flag
# Answer: ctf{zip_archive_comment}
flag_l2_2 = b'ctf{zip_archive_comment}'
zip_l2_2 = make_zip(
    [('readme.txt', b'This is a sample file.'),
     ('data.txt', b'Some data here.')],
    comment=flag_l2_2
)
save('zip_task2.zip', zip_l2_2)

# Task 3: PNG with 3 IDAT chunks
# Answer: ctf{3_idat_chunks}
png_l2_3 = make_minimal_png(idat_chunks=3)
save('png_task3.png', png_l2_3)

# Task 4: PNG with non-standard chunk name 'prNt' (looks like tEXt) containing flag
# Answer: ctf{custom_chunk_found}
flag_l2_4 = b'ctf{custom_chunk_found}'
png_l2_4 = make_minimal_png(extra_chunks=[
    (b'tEXt', b'Author\x00Test'),
    (b'prNt', b'Secret\x00' + flag_l2_4),
    (b'tEXt', b'Date\x002024'),
])
save('png_task4.png', png_l2_4)

# Task 5: password-protected ZIP, password = '1337'
# Answer: ctf{brute_force_zip}, password 1337
# Python's zipfile cannot CREATE encrypted ZIPs, only read them.
# So we embed a pre-computed encrypted ZIP (created once with system `zip`).
# Students extract with: zipfile.ZipFile.read(name, pwd=b'1337')
flag_l2_5 = b'ctf{brute_force_zip}'
enc_zip_b64 = (
    b'UEsDBAoACQAAALIbel0v5ifSIAAAABQAAAAIABwAZmxhZy50eHRVVAkAA5+nB2ufpwdrdXgLAAEE'
    b'6QMAAATpAwAAI45ce6pf4pKG9gHmaPjyAFlWqIjL6aKsGjSd8ZeSRFRQSwcIL+Yn0iAAAAAUAAAA'
    b'UEsBAh4DCgAJAAAAsht6XS/mJ9IgAAAAFAAAAAgAGAAAAAAAAQAAALSBAAAAAGZsYWcudHh0VVQF'
    b'AAOfpwdrdXgLAAEE6QMAAATpAwAAUEsFBgAAAAABAAEATgAAAHIAAAAAAA=='
)
import base64 as _b64
zip_l2_5 = _b64.b64decode(enc_zip_b64)
save('zip_task5.zip', zip_l2_5)

# Task 6: PNG with appended ZIP after IEND
# Answer: ctf{appended_zip_after_png}
flag_l2_6 = b'ctf{appended_zip_after_png}'
appended_zip6 = make_zip([('flag.txt', flag_l2_6)])
png_l2_6 = make_minimal_png(appended_after_iend=appended_zip6)
save('png_task6.png', png_l2_6)

# Task 7: Polyglot - PNG with valid IEND then ZIP
# Answer: ctf{png_view} (in tEXt) and ctf{zip_view} (in ZIP comment)
flag7_png = b'ctf{png_view}'
flag7_zip = b'ctf{zip_view}'
png7 = make_minimal_png(extra_chunks=[(b'tEXt', b'Secret\x00' + flag7_png)])
zip7 = make_zip([('note.txt', b'some note')], comment=flag7_zip)
polyglot = png7 + zip7
save('polyglot.bin', polyglot)

# Task 8: nested ZIPs (encrypted)
# Outer (no password): contains 'password_is_42.zip'
# Inner 1 (password '42'): contains 'try_1337.zip'
# Inner 2 (password '1337'): contains 'flag.txt' with flag
# Answer: ctf{nested_zip_matrioshka}
# Python's zipfile can't create encrypted ZIPs - embed pre-computed.
flag_l2_8 = b'ctf{nested_zip_matrioshka}'
nested_zip_b64 = (
    b'UEsDBAoAAAAAAMkbel1OqouopgEAAKYBAAASABwAcGFzc3dvcmRfaXNfNDIuemlwVVQJAAPKpwd'
    b'ryqcHa3V4CwABBOkDAAAE6QMAAFBLAwQKAAkAAADJG3pdmnl0hugAAADcAAAADAAcAHRyeV8xMzM'
    b'3LnppcFVUCQADyqcHa8qnB2t1eAsAAQTpAwAABOkDAAAFU4Eokj9CZL6+QA/IAPwLIWeLHaG+6Rb'
    b'CWe/GXn0gP+RLVM4Py9qseYf0RPAqLgbO/bq0R5BVwnmlwiMDTA1+Pm6+49KBBJfzy5/bEqeFdyB'
    b'IH4Z8xLLh44pxGvjKq6uuGKv6qru4u3TmgYhQtwBq9Rlz1tlo8CJGOpLxluOrP7O8D9JQECw2Fo'
    b'ZkiSto1PQGuelQ8rPTaJO3IuD6jqWtzPBiPwCnEqVl3C7iqJbCUnmS/mRdRbSVkRU0QhvcAf/TL'
    b'qd/wNqLPl98IJKYWpih0EcGMhkpzS87Aj/jrjTrwA9gkUoiiXnCUEsHCJp5dIboAAAA3AAAAFBLA'
    b'QIeAwoACQAAAMkbel2aeXSG6AAAANwAAAAMABgAAAAAAAAAAAC0gQAAAAB0cnlfMTMzNy56aXBVV'
    b'AUAA8qnB2t1eAsAAQTpAwAABOkDAABQSwUGAAAAAAEAAQBSAAAAPgEAAAAAUEsBAh4DCgAAAAAAy'
    b'Rt6XU6qi6imAQAApgEAABIAGAAAAAAAAAAAALSBAAAAAHBhc3N3b3JkX2lzXzQyLnppcFVUBQADy'
    b'qcHa3V4CwABBOkDAAAE6QMAAFBLBQYAAAAAAQABAFgAAADyAQAAAAA='
)
outer = _b64.b64decode(nested_zip_b64)
save('nested.zip', outer)

print("\nAll files created in:", os.path.abspath(OUT_DIR))
