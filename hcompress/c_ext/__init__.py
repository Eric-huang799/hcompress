"""C-accelerated hot paths — ctypes bindings to _hcompress.dll/.so.

Falls back gracefully to the pure-Python implementations if the shared
library cannot be loaded.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import c_int, c_size_t, c_uint32, c_uint8, POINTER, byref, cast

# ── Load shared library ─────────────────────────────────────────────────────

_lib = None
_lib_path = None

def _find_lib() -> str | None:
    """Search for the compiled shared library next to this file."""
    base = os.path.dirname(__file__)
    candidates = [
        os.path.join(base, "_hcompress.dll"),   # Windows
        os.path.join(base, "_hcompress.so"),     # Linux
        os.path.join(base, "_hcompress.dylib"),  # macOS
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None

try:
    _lib_path = _find_lib()
    if _lib_path:
        _lib = ctypes.CDLL(_lib_path)
except Exception:
    _lib = None

HAS_C_EXT = _lib is not None

# ── Type definitions ────────────────────────────────────────────────────────

if _lib:
    # BitBuf
    _lib.bitbuf_new.argtypes = [c_size_t]
    _lib.bitbuf_new.restype = ctypes.c_void_p

    _lib.bitbuf_free.argtypes = [ctypes.c_void_p]
    _lib.bitbuf_free.restype = None

    _lib.bitbuf_write.argtypes = [ctypes.c_void_p, c_uint32, c_int]
    _lib.bitbuf_write.restype = c_int

    _lib.bitbuf_flush.argtypes = [ctypes.c_void_p, POINTER(c_size_t)]
    _lib.bitbuf_flush.restype = ctypes.c_void_p

    # Bulk encode
    _lib.encode_bulk.argtypes = [
        ctypes.c_void_p, c_size_t,
        ctypes.c_void_p, ctypes.c_void_p,
    ]
    _lib.encode_bulk.restype = ctypes.c_void_p

    # Bulk decode
    _lib.decode_bulk.argtypes = [
        ctypes.c_void_p, c_size_t,
        ctypes.c_void_p, c_size_t,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        c_int,
    ]
    _lib.decode_bulk.restype = c_size_t

    # CRC-32
    _lib.crc32_compute.argtypes = [ctypes.c_void_p, c_size_t]
    _lib.crc32_compute.restype = c_uint32


# ── Python-facing wrappers ──────────────────────────────────────────────────


def c_encode_bulk(data: bytes, codes: list[int], bit_lengths: list[int]) -> bytes | None:
    """Encode *data* using the C bulk encoder.  Returns bytes or None on failure."""
    if not _lib:
        return None
    try:
        c_data = (c_uint8 * len(data))(*data)
        c_codes = (c_uint32 * 256)(*codes)
        c_blens = (c_uint8 * 256)(*bit_lengths)

        bb = _lib.bitbuf_new(max(len(data), 256))
        if not bb:
            return None
        # Use encode_bulk instead of per-byte write — much faster
        bb2 = _lib.encode_bulk(c_data, len(data), c_codes, c_blens)
        if not bb2:
            _lib.bitbuf_free(bb)
            return None
        out_len = c_size_t(0)
        ptr = _lib.bitbuf_flush(bb2, byref(out_len))
        if not ptr or out_len.value == 0:
            _lib.bitbuf_free(bb2)
            return None
        result = ctypes.string_at(ptr, out_len.value)
        _lib.bitbuf_free(bb2)
        return result
    except Exception:
        return None


def c_decode_bulk(
    compressed: bytes,
    base_code: list[int],
    symbol_offset: list[int],
    symbols_by_len: list[int],
    max_len: int,
    out_cap: int,
) -> bytes | None:
    """Decode *compressed* using the C bulk decoder.  Returns bytes or None."""
    if not _lib:
        return None
    try:
        c_comp = (c_uint8 * len(compressed))(*compressed)
        c_out = (c_uint8 * out_cap)()
        c_base = (c_int * len(base_code))(*base_code)
        c_off = (c_int * len(symbol_offset))(*symbol_offset)
        c_syms = (c_int * len(symbols_by_len))(*symbols_by_len)

        n = _lib.decode_bulk(c_comp, len(compressed), c_out, out_cap,
                              c_base, c_off, c_syms, max_len)
        if n == 0:
            return None
        return bytes(c_out[:n])
    except Exception:
        return None


def c_crc32(data: bytes) -> int:
    """Compute CRC-32 using C implementation."""
    if not _lib:
        return -1
    try:
        c_data = (c_uint8 * len(data))(*data)
        return int(_lib.crc32_compute(c_data, len(data)))
    except Exception:
        return -1


# ── Info ─────────────────────────────────────────────────────────────────────

def status() -> str:
    if _lib and _lib_path:
        return f"C extension loaded: {os.path.basename(_lib_path)}"
    return "C extension NOT available — using pure Python fallback"
