"""Bit-level I/O streams for Huffman encoding / decoding.

BitWriter — accumulates bits and flushes to a byte buffer.
BitReader — reads individual bits from a bytes buffer.

Both operate MSB-first: when writing code=0b101 with nbits=3,
the bits 1, 0, 1 are emitted in that order.
"""

from __future__ import annotations


class BitWriter:
    """Write individual bits to an in-memory byte buffer.

    Bits are packed into bytes LSB-first within each byte (first bit
    written becomes bit 0 of byte 0), but the *code value* is consumed
    MSB-first — see :meth:`write_bits`.

    Typical usage::

        bw = BitWriter()
        bw.write_bits(0b0, 1)    # code for 'A'
        bw.write_bits(0b10, 2)   # code for 'B'
        compressed = bw.flush()  # → bytes ready to write to file
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._current_byte: int = 0
        self._bits_in_current: int = 0
        self._total_bits: int = 0

    # ── write ────────────────────────────────────────────────────────────

    def write_bits(self, value: int, nbits: int) -> None:
        """Write the lower *nbits* of *value*, MSB first.

        Example:
            write_bits(0b101, 3) emits bit 2 (=1), bit 1 (=0), bit 0 (=1).
        """
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
        """Pad any partial byte with zeros and return the full byte buffer."""
        if self._bits_in_current > 0:
            self._buffer.append(self._current_byte)
            self._current_byte = 0
            self._bits_in_current = 0
        return bytes(self._buffer)

    # ── query ────────────────────────────────────────────────────────────

    def tell_bytes(self) -> int:
        """Number of *full* bytes written so far (before flush)."""
        return len(self._buffer)

    def tell_bits(self) -> int:
        """Total bits written."""
        return self._total_bits


class BitReader:
    """Read individual bits from a bytes buffer.

    Bits are consumed in the same order they were written: LSB-first
    within each byte, and the bits themselves were emitted MSB-first
    by :class:`BitWriter`.

    Typical usage::

        br = BitReader(compressed_data)
        while not br.exhausted():
            bit = br.read_bits(1)
            ...  # walk decode tree / lookup table
    """

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._byte_pos: int = 0
        self._bit_pos: int = 0  # 0 = LSB of current byte
        self._total_bits: int = 0

    # ── read ─────────────────────────────────────────────────────────────

    def read_bits(self, nbits: int) -> int:
        """Read *nbits* bits and return them as a uint32, MSB first.

        The first bit read becomes the MSB of the returned value.

        Raises:
            EOFError: not enough bits remaining.
        """
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
        """Read a single bit (convenience wrapper). Returns 0 or 1."""
        return self.read_bits(1)

    # ── query ────────────────────────────────────────────────────────────

    def tell_bits(self) -> int:
        """Total bits read so far."""
        return self._total_bits

    def tell_bytes(self) -> int:
        """Bytes consumed so far (rounded down to full bytes)."""
        return self._byte_pos

    def exhausted(self) -> bool:
        """True when all bits have been consumed."""
        return self._byte_pos >= len(self._data)
