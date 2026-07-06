"""HCF (Huffman Compressed File) header format.

Layout
------
Offset  Size  Field
------  ----  -----
0       4     Magic:  'H' 'C' 'F' 0x1A
4       2     Version  (uint16 LE, v1 = 0x0001)
6       2     Flags    (uint16 LE, see below)
8       2     CRC-16   (of header with this field zeroed)
10      2     N = symbol count (uint16 LE, typically 256)
12      N     Bit-length table (one uint8 per symbol, 0 = absent)
12+N    8     Original size in bytes (uint64 LE)
20+N    4     Extension length E (uint32 LE, only if flags & HAS_EXT)
24+N    E     Extension data (UTF-8 JSON, only if flags & HAS_EXT)
-----   ---   ---- end of header ----
...    ...    Compressed bitstream, padded to byte boundary

Flags (uint16 LE)
-----------------
bit 0       HAS_EXTENSION_DATA — extension data follows original_size
bits 1-4    COMPRESSION_LEVEL  — 0-9 (default 6)
bits 5-7    ENTROPY_CODER_ID   — 0=CanonicalHuffman, 1-7 reserved
bits 8-15   Reserved (must be 0)
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field

# ── constants ────────────────────────────────────────────────────────────────

MAGIC = b"HCF\x1a"
VERSION_V1 = 0x0001
ALPHABET_SIZE = 256

# Flag bits
FLAG_HAS_EXTENSION = 1 << 0
FLAG_LEVEL_SHIFT = 1
FLAG_LEVEL_MASK = 0xF           # 4 bits
FLAG_CODER_SHIFT = 5
FLAG_CODER_MASK = 0x7           # 3 bits
FLAG_DIRECTORY = 1 << 8         # bit 8: archive contains a directory tree

# Entropy coder IDs
CODER_CANONICAL_HUFFMAN = 0

# CRC-16/CCITT-FALSE parameters
CRC16_POLY = 0x1021
CRC16_INIT = 0xFFFF

# ── CRC-16 (table-driven) ────────────────────────────────────────────────────


def _make_crc16_table() -> list[int]:
    t: list[int] = []
    for i in range(256):
        crc = i << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ CRC16_POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
        t.append(crc)
    return t


_CRC16_TABLE = _make_crc16_table()


def _crc16(data: bytes) -> int:
    crc = CRC16_INIT
    for byte in data:
        idx = ((crc >> 8) ^ byte) & 0xFF
        crc = ((crc << 8) ^ _CRC16_TABLE[idx]) & 0xFFFF
    return crc


# ── header dataclass ─────────────────────────────────────────────────────────


@dataclass
class HeaderInfo:
    """Parsed HCF file header."""

    version: int
    flags: int
    bit_lengths: list[int]              # 256 elements, 0 = symbol absent
    original_size: int
    extension_data: bytes = b""         # raw UTF-8 JSON bytes

    # --- derived properties ---

    @property
    def compression_level(self) -> int:
        return (self.flags >> FLAG_LEVEL_SHIFT) & FLAG_LEVEL_MASK

    @property
    def coder_id(self) -> int:
        return (self.flags >> FLAG_CODER_SHIFT) & FLAG_CODER_MASK

    @property
    def has_extension(self) -> bool:
        return bool(self.flags & FLAG_HAS_EXTENSION)


# ── read / write ─────────────────────────────────────────────────────────────


def write_header(
    f,
    bit_lengths: list[int],
    original_size: int,
    flags: int = 0,
    extension_data: bytes = b"",
) -> int:
    """Write HCF header to a writable binary stream.

    Returns the total number of header bytes written.
    """
    # Validate
    assert len(bit_lengths) == ALPHABET_SIZE, "bit_lengths must be 256 elements"

    if extension_data:
        flags |= FLAG_HAS_EXTENSION

    # Build header (excluding CRC field at offset 8-9)
    header = bytearray()
    header += MAGIC                                           # 0-3
    header += struct.pack("<H", VERSION_V1)                   # 4-5
    header += struct.pack("<H", flags)                        # 6-7
    header += b"\x00\x00"                                     # 8-9 CRC placeholder
    header += struct.pack("<H", ALPHABET_SIZE)                # 10-11
    header += bytes(bit_lengths)                              # 12 … 12+255
    header += struct.pack("<Q", original_size)                # 12+256 … 12+256+7

    if flags & FLAG_HAS_EXTENSION:
        ext = extension_data if isinstance(extension_data, bytes) else extension_data.encode("utf-8")
        header += struct.pack("<I", len(ext))                 # extension length
        header += ext                                         # extension data

    # Compute CRC-16 over everything except the CRC field itself
    crc_input = bytes(header[:8]) + bytes(header[10:])
    crc = _crc16(crc_input)
    struct.pack_into("<H", header, 8, crc)

    f.write(bytes(header))
    return len(header)


def read_header(f) -> HeaderInfo:
    """Read and validate an HCF header from a readable binary stream.

    Raises:
        ValueError: bad magic, unsupported version, CRC mismatch.
        EOFError: truncated header.
    """
    # Read fixed portion (up to original size, excluding extension)
    # Fixed: 4(magic)+2(ver)+2(flags)+2(crc)+2(N)+256(bl)+8(orig) = 276
    fixed = _read_exact(f, 276)

    magic = fixed[0:4]
    if magic != MAGIC:
        raise ValueError(
            f"Bad magic: expected {MAGIC!r}, got {magic!r}. "
            f"Not an HCF file?"
        )

    version = struct.unpack_from("<H", fixed, 4)[0]
    if version != VERSION_V1:
        raise ValueError(
            f"Unsupported HCF version {version}. "
            f"This tool supports v{VERSION_V1} only."
        )

    flags = struct.unpack_from("<H", fixed, 6)[0]
    crc_stored = struct.unpack_from("<H", fixed, 8)[0]
    n_symbols = struct.unpack_from("<H", fixed, 10)[0]

    bit_lengths = list(fixed[12:12 + n_symbols])

    # Pad to 256 if fewer symbols stored
    if n_symbols < ALPHABET_SIZE:
        bit_lengths += [0] * (ALPHABET_SIZE - n_symbols)
    elif n_symbols > ALPHABET_SIZE:
        raise ValueError(f"Symbol count {n_symbols} > {ALPHABET_SIZE}")

    original_size = struct.unpack_from("<Q", fixed, 12 + n_symbols)[0]

    # Read extension data
    extension_data = b""
    if flags & FLAG_HAS_EXTENSION:
        ext_len_bytes = _read_exact(f, 4)
        ext_len = struct.unpack("<I", ext_len_bytes)[0]
        if ext_len > 0:
            extension_data = _read_exact(f, ext_len)

    # Verify CRC-16 (same layout as write path: skip the CRC field at offset 8-9)
    header_for_crc = bytearray(fixed[:8])            # magic + version + flags
    header_for_crc += fixed[10:]                     # N + bit_lengths + original_size
    if extension_data:
        header_for_crc += struct.pack("<I", len(extension_data))
        header_for_crc += extension_data
    if _crc16(bytes(header_for_crc)) != crc_stored:
        raise ValueError("Header CRC-16 mismatch — file may be corrupted")

    return HeaderInfo(
        version=version,
        flags=flags,
        bit_lengths=bit_lengths,
        original_size=original_size,
        extension_data=extension_data,
    )


def _read_exact(f, n: int) -> bytes:
    """Read exactly *n* bytes from *f*, raising EOFError on short read."""
    data = f.read(n)
    if len(data) < n:
        raise EOFError(
            f"Truncated HCF file: expected {n} bytes, got {len(data)}"
        )
    return data


# ── extension data helpers ───────────────────────────────────────────────────


def pack_extension_json(extensions: list) -> bytes:
    """Serialize registered extensions' data to the HCF header JSON blob.

    Each extension contributes a dict keyed by its ``extension_id``.
    The result is a UTF-8 JSON object (possibly empty).
    """
    payload: dict[str, dict] = {}
    for ext in extensions:
        try:
            data = ext.get_extension_data()
        except Exception:
            data = {}
        if data:
            payload[ext.extension_id] = data
    if not payload:
        return b""
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def unpack_extension_json(raw: bytes, extensions: list) -> None:
    """Deserialize HCF header extension JSON back into extension instances.

    Each extension's ``set_extension_data()`` is called with its slice
    of the payload (or an empty dict if not present).
    """
    if not raw:
        return
    try:
        payload: dict = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    for ext in extensions:
        try:
            ext.set_extension_data(payload.get(ext.extension_id, {}))
        except Exception:
            pass
