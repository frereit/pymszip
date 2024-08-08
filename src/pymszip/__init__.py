__version__ = "1.0.1"

import struct
import binascii
import zlib

HEADER = "<6BBBQQ"
CHUNK_HEADER = "<IH"
CHUNK_PADDING = 0x4B43  # b"CK" in little endian
MAX_CHUNK_SIZE = 2**15

# 0a51e5c0180 is hardcoded in Cabinet.dll.Compress
MAGIC_BYTES = [10, 81, 229, 192, 24, 0]

# https://learn.microsoft.com/en-us/windows/win32/api/compressapi/nf-compressapi-createcompressor#parameters
COMPRESS_ALGORITHM = {
    "MSZIP": 2,
    "XPRESS": 3,
    "XPRESS_HUFF": 4,
    "LZMS": 5,
}


def decompress(compressed: bytes) -> bytes:
    """
    Decompresss a MSZIP compressed buffer.

    Args:
        compressed (bytes): The compressed buffer.

    Returns:
        bytes: The decompressed bytes.

    Raises:
        ValueError: If the data is malformed, e.g. because of an invalid header value, a ValueError is raised.
    """
    (
        *magic,
        actual_crc,
        algorithm,
        decompressed_length,
        first_chunk_decompressed_length,
    ) = struct.unpack_from(HEADER, compressed)
    # Check Magic Bytes
    if magic != MAGIC_BYTES:
        raise ValueError(
            f"Invalid magic bytes. Expected {bytes(MAGIC_BYTES).hex()}, got {bytes(magic).hex()}"
        )

    # Check for MSZIP algorithm. The others use the same header format.
    if algorithm != COMPRESS_ALGORITHM["MSZIP"]:
        actual_algorithm = str(algorithm)
        if algorithm in COMPRESS_ALGORITHM.keys():
            actual_algorithm = next(
                algo[0] for algo in COMPRESS_ALGORITHM.items() if algo[1] == algorithm
            )
        raise ValueError(
            f"Unsupported Algorithm Expected MSZIP, got {actual_algorithm}"
        )

    # Calculate the CRC. This calculation is taken from Cabinet.dll.Compress
    expected_crc = (
        binascii.crc32(compressed[7:24], binascii.crc32(compressed[:6])) & 0xFF
    )
    if actual_crc != expected_crc:
        raise ValueError(
            f"CRC does not match. Expected {expected_crc}, got {actual_crc}"
        )

    current_offset = struct.calcsize(HEADER)
    decompressed = bytearray()
    while current_offset < len(compressed):
        (compressed_chunk_size, padding_bytes) = struct.unpack_from(
            CHUNK_HEADER, compressed, current_offset
        )

        if padding_bytes != CHUNK_PADDING:
            raise ValueError(
                f"Invalid chunk padding. Expected {CHUNK_PADDING:x}, got {padding_bytes:x}"
            )

        # The compressed chunk size includes the 2 padding bytes which are not part of the compressed zlib data.
        compressed_chunk_size -= 2

        current_offset += struct.calcsize(CHUNK_HEADER)

        decompressor = zlib.decompressobj(-zlib.MAX_WBITS, decompressed)
        decompressed_chunk = decompressor.decompress(
            compressed[current_offset : current_offset + compressed_chunk_size]
        )
        if len(decompressed) == 0:
            # First chunk
            if len(decompressed_chunk) != first_chunk_decompressed_length:
                raise ValueError(
                    f"first chunk decompressed to {len(decompressed_chunk)} bytes, expected {first_chunk_decompressed_length} bytes"
                )
        current_offset += compressed_chunk_size

        decompressed.extend(decompressed_chunk)

    if decompressed_length != len(decompressed):
        raise ValueError(
            f"decompressed data length does not match. Expected {decompressed_length}, got {len(decompressed)}"
        )

    return bytes(decompressed)


def compress(decompressed: bytes, zlib_level=9) -> bytes:
    """
    Compress a buffer using the MSZIP algorithm.

    Note:
        The output of this function is not guaranteed to match the output of
        the corresponding Windows API (CreateCompressor / Compress), because
        the zlib parameters can differ. However, the output is fully
        compatible with the Windows format. Any output of this function that
        cannot be decompressed by the Windows API is considered a bug in
        pymszip and should be reported on the issue tracker.

    Args:
        decompressed (bytes): The decompressed bytes.
        zlib_level (int): Passed to zlib's `compressorobj`.
        The compression level (an integer in the range 0-9 or -1;
        default is currently equivalent to 6).
        Higher compression levels are slower, but produce smaller results.

    Returns:
        bytes: The compressed data.
    """

    algorithm = COMPRESS_ALGORITHM["MSZIP"]
    decompressed_length = len(decompressed)
    first_chunk_decompressed_length = min(len(decompressed), MAX_CHUNK_SIZE)

    header_no_crc = struct.pack(
        HEADER,
        *MAGIC_BYTES,
        0,
        algorithm,
        decompressed_length,
        first_chunk_decompressed_length,
    )
    actual_crc = (
        binascii.crc32(header_no_crc[7:24], binascii.crc32(header_no_crc[:6])) & 0xFF
    )
    compressed = bytearray(struct.pack(
        HEADER,
        *MAGIC_BYTES,
        actual_crc,
        algorithm,
        decompressed_length,
        first_chunk_decompressed_length,
    ))

    current_zdict = bytearray()
    while decompressed:
        chunk = decompressed[:MAX_CHUNK_SIZE]
        decompressed = decompressed[MAX_CHUNK_SIZE:]

        compressor = zlib.compressobj(
            wbits=-zlib.MAX_WBITS,
            zdict=current_zdict,
            level=zlib_level,
            memLevel=9,  # This is required for Windows API compatibility.
        )

        chunk_compressed = compressor.compress(chunk) + compressor.flush()
        # +2 is the 2 padding bytes (CHUNK_PADDING), which are included in the chunk length but not part of the zlib stream.
        compressed.extend(struct.pack(CHUNK_HEADER, len(chunk_compressed) + 2, CHUNK_PADDING))
        compressed.extend(chunk_compressed)

        current_zdict.extend(chunk)

    return bytes(compressed)
