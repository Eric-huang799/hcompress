"""Parallel block compression / decompression using ProcessPoolExecutor.

Multi-block HCF format (extended):
    [standard HCF header with FLAG_MULTI_BLOCK set]
    [4 bytes: block_count (uint32 LE)]
    [for each block:
        [4 bytes: block_size (uint32 LE) — compressed bytes]
        [block_size bytes: compressed block data]
    ]

Each block is an independent mini-HCF stream.  Blocks are
compressed/decompressed in parallel using multiple processes
to bypass the Python GIL.
"""

from __future__ import annotations

import os
import struct
from concurrent.futures import ProcessPoolExecutor, as_completed

from hcompress.canonical import freq_table, canonical_from_freq, build_decode_table, decode_symbol, encode_data
from hcompress.bitstream import BitWriter, BitReader
from hcompress.format import MAGIC, VERSION_V1, FLAG_HAS_EXTENSION, _crc16

FLAG_MULTI_BLOCK = 1 << 9  # bit 9


def _compress_block(args) -> bytes:
    """Compress a single block (picklable for ProcessPoolExecutor)."""
    data, level = args
    freq = freq_table(data)
    codes, blens = canonical_from_freq(freq)

    # Try C extension first
    try:
        from hcompress.c_ext import c_encode_bulk
        encoded = c_encode_bulk(data, codes, blens)
    except Exception:
        writer = BitWriter()
        encode_data(writer, data, codes, blens)
        encoded = writer.flush()

    header = bytearray()
    header += MAGIC
    header += struct.pack("<H", VERSION_V1)
    flags = ((level & 0xF) << 1)
    header += struct.pack("<H", flags)
    header += b"\x00\x00"
    header += struct.pack("<H", 256)
    header += bytes(blens)
    header += struct.pack("<Q", len(data))
    crc = _crc16(bytes(header[:8]) + bytes(header[10:]))
    struct.pack_into("<H", header, 8, crc)
    return bytes(header) + encoded


def _decompress_block(data: bytes) -> bytes:
    """Decompress a single mini-HCF block (picklable)."""
    blens = list(data[12:268])
    original_size = struct.unpack_from("<Q", data, 268)[0]
    payload = data[276:]

    # Try C extension first
    try:
        from hcompress.c_ext import c_decode_bulk
        base_code, sym_off, syms_by_len, max_len = build_decode_table(blens)
        flat = []
        off = [0]
        for lst in syms_by_len:
            off.append(off[-1] + len(lst))
            flat.extend(lst)
        result = c_decode_bulk(payload, base_code, off, flat, max_len, original_size)
        if result is not None:
            return result
    except Exception:
        pass

    base_code, sym_off, syms_by_len, max_len = build_decode_table(blens)
    reader = BitReader(payload)
    decoded = bytearray()
    for _ in range(original_size):
        decoded.append(decode_symbol(reader, base_code, sym_off, syms_by_len, max_len))
    return bytes(decoded)


def compress_parallel(
    input_path: str, output_path: str, level: int = 6, workers: int = 4
) -> dict:
    """Compress a file using multiple threads.  Returns stats dict."""
    import os, time
    t0 = time.perf_counter()

    with open(input_path, "rb") as f:
        data = f.read()

    block_size = max(len(data) // workers, 65536)
    blocks = [data[i:i + block_size] for i in range(0, len(data), block_size)]

    # Compress blocks in parallel (bypass GIL with processes)
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_compress_block, (b, level)): i for i, b in enumerate(blocks)}
        for f in as_completed(futures):
            idx = futures[f]
            results.append((idx, f.result()))
    results.sort(key=lambda x: x[0])
    compressed_blocks = [r[1] for r in results]

    # Write output
    with open(output_path, "wb") as f:
        # Main header
        main = bytearray()
        main += MAGIC
        main += struct.pack("<H", VERSION_V1)
        main += struct.pack("<H", FLAG_MULTI_BLOCK)
        main += b"\x00\x00"
        main += struct.pack("<H", 256)
        main += bytes([0]*256)  # bit_lengths placeholder
        main += struct.pack("<Q", len(data))
        crc = _crc16(bytes(main[:8]) + bytes(main[10:]))
        struct.pack_into("<H", main, 8, crc)
        f.write(bytes(main))
        f.write(struct.pack("<I", len(compressed_blocks)))
        for block in compressed_blocks:
            f.write(struct.pack("<I", len(block)))
            f.write(block)

    elapsed = (time.perf_counter() - t0) * 1000
    comp_size = os.path.getsize(output_path)
    return {
        "original_size": len(data), "compressed_size": comp_size,
        "ratio": comp_size / max(len(data), 1),
        "elapsed_ms": elapsed, "workers": workers,
    }


def decompress_parallel(input_path: str, output_path: str, workers: int = 4) -> dict:
    """Decompress a multi-block HCF file using multiple threads."""
    import os, time
    t0 = time.perf_counter()

    with open(input_path, "rb") as f:
        # Read main header
        main = f.read(276)
        original_size = struct.unpack_from("<Q", main, 268)[0]
        block_count = struct.unpack("<I", f.read(4))[0]

        blocks = []
        for _ in range(block_count):
            blen = struct.unpack("<I", f.read(4))[0]
            blocks.append(f.read(blen))

    # Decompress blocks in parallel (bypass GIL with processes)
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_decompress_block, b): i for i, b in enumerate(blocks)}
        for f in as_completed(futures):
            idx = futures[f]
            results.append((idx, f.result()))
    results.sort(key=lambda x: x[0])
    data = b"".join(r[1] for r in results)

    with open(output_path, "wb") as f:
        f.write(data)

    elapsed = (time.perf_counter() - t0) * 1000
    return {"original_size": len(data), "elapsed_ms": elapsed, "workers": workers}
