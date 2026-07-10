"""CRC-32 checksum — default integrity verification for HCF files (same as gzip/zip/PNG).

Polynomial 0xEDB88320 (reflected), init=0xFFFFFFFF, final XOR=0xFFFFFFFF.
"""

from __future__ import annotations

# ── CRC-32 lookup table ──────────────────────────────────────────────────────


def _make_table() -> list[int]:
    table: list[int] = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
        table.append(crc)
    return table


_CRC_TABLE: list[int] = _make_table()


# ── public API ───────────────────────────────────────────────────────────────


def crc32(data: bytes, crc: int = 0) -> int:
    """Compute CRC-32 over *data*, return value before final XOR."""
    crc = crc ^ 0xFFFFFFFF
    for byte in data:
        idx = (crc ^ byte) & 0xFF
        crc = _CRC_TABLE[idx] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def crc32_digest(data: bytes) -> bytes:
    return crc32(data).to_bytes(4, "big")


# ── IChecksum-compatible wrapper ─────────────────────────────────────────────


class CRC32:
    """CRC-32 integrity checker — conforms to IChecksum. checksum_id=0, digest_size=4."""

    checksum_id: int = 0
    digest_size: int = 4

    @staticmethod
    def compute(data: bytes) -> bytes:
        return crc32_digest(data)

    @staticmethod
    def verify(data: bytes, expected: bytes) -> bool:
        if len(expected) != 4:
            return False
        return crc32_digest(data) == expected
