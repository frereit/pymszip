# pymszip

This library fills the very niche use-case where you have data compressed using [`CreateCompressor`](https://learn.microsoft.com/en-us/windows/win32/api/compressapi/nf-compressapi-createcompressor) / [`Compress`](https://learn.microsoft.com/en-us/windows/win32/api/compressapi/nf-compressapi-compress) with the MSZIP algorithm, and want to decompress it without the Windows API (e.g. under Linux), or the other way around and you want to create compressed data that can be decompressed by the Windows API.

## Installation

```bash
pip install pymszip
```

Alternatively, install directly from GitHub:

```bash
pip install git+https://github.com/frereit/pymszip
```

## Usage

```python
import pymszip

compressed = pymszip.compress(b"Hello, world!")
decompressed = pymszip.decompress(compressed)

print(decompressed)
```

## Goals and non-goals

This repo aims to provide full compatibility with the Windows API. This means that:

- Any data compressed using the Windows API can be decompressed by `pymszip`
- Any data compressed using `pymszip` can be decompressed by the Windows API

If you find data where either of this isn't the case, please file an issue if you can!

However, this library does not aim to produce identical results to the Windows compression. This means data compressed using `pymszip` may yield different results than if it was compressed with the Windows API. This is to be expected because of slightly differing zlib parameters, but not an issue, as long as compatibility is preserved.

## MSZIP format

The MSZIP compression format is a proprietary compression format developed by Microsoft, based on the `zlib` compression library.

Under the hood, MSZIP compressed data is prefixed with a 24 byte header, and an arbitrary number of compressed chunks following it.

The header consiss of 6 magic bytes (`0a51e5c01800`)[^magic], followed by 1 CRC byte, 1 byte to identify the algorithm (`MSZIP` / `02`), followed by 8 bytes little-endian integer to specify the decompressed size of the data, and another 8 bytes little-endian integer to specify the decompressed size of the first chunk.

Each chunk is prefixed with a 4 byte little-endian integer to specify its size, and 2 magic bytes ("CK"), after which a zlib-compressed stream follows. The "size" of the chunk includes the zlib stream, and the 2 magic bytes, but not the size header itself.

To decompress data, each zlib-compressed stream is decompressed individually, however each chunk must be given all previously decompressed data as the `zdict` used during decompression.

To compress data, a similar process is followed. Experimentially, I came to the conclusion that the `memLevel` must be set to 9`, or Windows will not be able to decompress the compressed data again in some cases.
