"""Bit-level I/O streams for Huffman encoding / decoding.

BitWriter — accumulates bits and flushes to a byte buffer.
BitReader — reads individual bits from a bytes buffer.
"""

from __future__ import annotations


class BitWriter:
    """Write individual bits to an in-memory byte buffer.

        bw = BitWriter()
        bw.write_bits(0b0, 1)
        bw.write_bits(0b10, 2)
        compressed = bw.flush()
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._current_byte: int = 0
        self._bits_in_current: int = 0
        self._total_bits: int = 0

    # ── write ────────────────────────────────────────────────────────────

    def write_bits(self, value: int, nbits: int) -> None:
        if nbits <= 0:
            return
        for i in range(nbits - 1, -1, -1):
            bit = (value >> i) & 1
            self._current_byte |= bit << self._bits_in_current
            self._bits_in_current += 1
            self._total_bits += 1
            if self._bits_in_current == 8:
                self._buffer.append(self._current_byte)
                self._current_byte = 0
                self._bits_in_current = 0

    # ── finalise ─────────────────────────────────────────────────────────

    def flush(self) -> bytes:
        if self._bits_in_current > 0:
            self._buffer.append(self._current_byte)
            self._current_byte = 0
            self._bits_in_current = 0
        return bytes(self._buffer)

    # ── query ────────────────────────────────────────────────────────────

    def tell_bytes(self) -> int:
        return len(self._buffer)

    def tell_bits(self) -> int:
        return self._total_bits


class BitReader:
    """Read individual bits from a bytes buffer.

        br = BitReader(compressed_data)
        while not br.exhausted():
            bit = br.read_bits(1)
    """

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._byte_pos: int = 0
        self._bit_pos: int = 0  # 0 = LSB of current byte
        self._total_bits: int = 0

    # ── read ─────────────────────────────────────────────────────────────

    def read_bits(self, nbits: int) -> int:
        if nbits <= 0:
            return 0
        value = 0
        for _ in range(nbits):
            if self._byte_pos >= len(self._data):
                raise EOFError(
                    f"Unexpected end of bitstream at byte {self._byte_pos}"
                )
            byte = self._data[self._byte_pos]
            bit = (byte >> self._bit_pos) & 1
            value = (value << 1) | bit
            self._bit_pos += 1
            self._total_bits += 1
            if self._bit_pos == 8:
                self._byte_pos += 1
                self._bit_pos = 0
        return value

    def read_bit(self) -> int:
        return self.read_bits(1)

    # ── query ────────────────────────────────────────────────────────────

    def tell_bits(self) -> int:
        return self._total_bits

    def tell_bytes(self) -> int:
        return self._byte_pos

    def exhausted(self) -> bool:
        return self._byte_pos >= len(self._data)
