import ctypes
import ctypes.wintypes
from enum import Enum
import os

import pymszip


# https://learn.microsoft.com/en-us/windows/win32/api/compressapi/nf-compressapi-createcompressor#parameters
class COMPRESS_ALGORITHM(Enum):
    COMPRESS_ALGORITHM_MSZIP = 2
    COMPRESS_ALGORITHM_XPRESS = 3
    COMPRESS_ALGORITHM_XPRESS_HUFF = 4
    COMPRESS_ALGORITHM_LZMS = 5


GetLastError = ctypes.windll.kernel32.GetLastError
GetLastError.restype = ctypes.wintypes.INT

CreateCompressor = ctypes.windll.cabinet.CreateCompressor
CreateCompressor.argtypes = (
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.wintypes.HANDLE),
)
CreateCompressor.restype = ctypes.wintypes.BOOL

Compress = ctypes.windll.cabinet.Compress
Compress.argtypes = (
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
)
Compress.restype = ctypes.wintypes.BOOL

CreateDecompressor = ctypes.windll.cabinet.CreateDecompressor
CreateDecompressor.argtypes = (
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.wintypes.HANDLE),
)
CreateDecompressor.restype = ctypes.wintypes.BOOL

Decompress = ctypes.windll.cabinet.Decompress
Decompress.argtypes = (
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
)
Decompress.restype = ctypes.wintypes.BOOL


def winapi_compress(data: bytes) -> bytes:
    hCompressor = ctypes.wintypes.HANDLE()
    if (
        CreateCompressor(
            COMPRESS_ALGORITHM.COMPRESS_ALGORITHM_MSZIP.value,
            ctypes.c_void_p(),
            ctypes.byref(hCompressor),
        )
        == 0
    ):
        raise RuntimeError("Failed to create compressor")

    data_buffer = (ctypes.c_uint8 * len(data))(*data)
    data_ptr = ctypes.c_void_p(ctypes.addressof(data_buffer))

    out_size = ctypes.c_size_t(0)
    if (
        Compress(
            hCompressor,
            data_ptr,
            len(data),
            ctypes.c_void_p(),
            0,
            ctypes.byref(out_size),
        )
        == 1
    ):
        raise RuntimeError(
            "Unreachable. Tried to compress into a 0 byte buffer to get the size, but got a successful compression."
        )

    output_buffer = (ctypes.c_uint8 * out_size.value)()
    out_ptr = ctypes.c_void_p(ctypes.addressof(output_buffer))
    if (
        Compress(
            hCompressor,
            data_ptr,
            len(data),
            out_ptr,
            out_size.value,
            ctypes.byref(out_size),
        )
        == 0
    ):
        raise RuntimeError("Failed to compress data")

    return bytes(output_buffer[0 : out_size.value])


def winapi_decompress(data: bytes) -> bytes:
    hDecompressor = ctypes.wintypes.HANDLE()
    if (
        CreateDecompressor(
            COMPRESS_ALGORITHM.COMPRESS_ALGORITHM_MSZIP.value,
            ctypes.c_void_p(),
            ctypes.byref(hDecompressor),
        )
        == 0
    ):
        raise RuntimeError("Failed to create decompressor")

    data_buffer = (ctypes.c_uint8 * len(data))(*data)
    data_ptr = ctypes.c_void_p(ctypes.addressof(data_buffer))

    out_size = ctypes.c_size_t(0)
    if (
        Decompress(
            hDecompressor,
            data_ptr,
            len(data),
            ctypes.c_void_p(),
            0,
            ctypes.byref(out_size),
        )
        == 1
    ):
        raise RuntimeError(
            "Unreachable. Tried to decompress into a 0 byte buffer to get the size, but got a successfull decompression."
        )

    output_buffer = (ctypes.c_uint8 * out_size.value)()
    out_ptr = ctypes.c_void_p(ctypes.addressof(output_buffer))
    if (
        Decompress(
            hDecompressor,
            data_ptr,
            len(data),
            out_ptr,
            out_size.value,
            ctypes.byref(out_size),
        )
        == 0
    ):
        print(f"{GetLastError()=}")
        raise RuntimeError("Failed to decompress data")

    return bytes(output_buffer[0 : out_size.value])


def gen_testcases():
    yield b"\x00"
    for i in range(1, 1000):
        yield os.urandom(i * 100)


def test_windows_can_decompress_windows_data():
    # Make sure we're calling the Windows API correctly.
    for tc in gen_testcases():
        compressed = winapi_compress(tc)
        decomp = winapi_decompress(compressed)
        assert decomp == tc, f"{tc.hex()}"


def test_pymszip_can_decompress_windows_data():
    for tc in gen_testcases():
        compressed = winapi_compress(tc)
        decomp = pymszip.decompress(compressed)
        assert decomp == tc, f"{tc.hex()}"


def test_windows_can_decompress_pymszip_data():
    for tc in gen_testcases():
        compressed = pymszip.compress(tc)
        try:
            decomp = winapi_decompress(compressed)
        except RuntimeError:
            decomp = b""
        assert decomp == tc, f"{tc.hex()}"


def test_pymszip_can_decompress_pymszip_data():
    for tc in gen_testcases():
        compressed = pymszip.compress(tc)
        decomp = pymszip.decompress(compressed)
        assert decomp == tc, f"{tc.hex()}"


def main():
    test_windows_can_decompress_windows_data()
    test_pymszip_can_decompress_pymszip_data()
    test_pymszip_can_decompress_windows_data()
    test_windows_can_decompress_pymszip_data()


if __name__ == "__main__":
    main()
