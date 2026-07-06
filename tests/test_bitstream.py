"""Tests for bitstream.py — BitWriter / BitReader."""

import pytest
from hcompress.bitstream import BitWriter, BitReader


class TestBitWriter:
    def test_single_bit(self):
        bw = BitWriter()
        bw.write_bits(1, 1)
        assert bw.flush() == b"\x01"
        assert bw.tell_bits() == 1

    def test_write_byte_msb_first(self):
        bw = BitWriter()
        bw.write_bits(0b101, 3)   # MSB first: 1,0,1
        bw.write_bits(0b0, 1)
        bw.write_bits(0b11, 2)    # 1,1
        # Byte 0: bits [1,0,1,0,1,1,0,0] → bit0=1, bit1=0, bit2=1, bit3=0, bit4=1, bit5=1
        # Value: 0b00110101 = 0x35
        result = bw.flush()
        assert result == b"\x35"

    def test_flush_pads_zero(self):
        bw = BitWriter()
        bw.write_bits(0b1, 1)
        data = bw.flush()
        # Only 1 bit written, remaining 7 bits are zero
        assert data == b"\x01"

    def test_multiple_bytes(self):
        bw = BitWriter()
        for _ in range(20):
            bw.write_bits(0xFF, 8)
        data = bw.flush()
        assert data == b"\xff" * 20

    def test_tell_bytes(self):
        bw = BitWriter()
        bw.write_bits(0xFF, 8)
        assert bw.tell_bytes() == 1
        bw.write_bits(0xFF, 8)
        assert bw.tell_bytes() == 2

    def test_nbits_zero(self):
        bw = BitWriter()
        bw.write_bits(0xFF, 0)
        assert bw.flush() == b""
        assert bw.tell_bits() == 0


class TestBitReader:
    def test_read_single_bit(self):
        br = BitReader(b"\x01")
        assert br.read_bits(1) == 1

    def test_read_msb_first(self):
        # BitWriter wrote 0b101 (3 bits) + 0b0 + 0b11 → byte = 0x35
        br = BitReader(b"\x35")
        assert br.read_bits(3) == 0b101
        assert br.read_bits(1) == 0b0
        assert br.read_bits(2) == 0b11

    def test_read_full_bytes(self):
        # BitWriter inverts bit order within bytes (LSB-first packing).
        # Writing 0xAB, 0xCD produces bytes 0xD5, 0xB3 in the buffer.
        bw = BitWriter()
        bw.write_bits(0xAB, 8)
        bw.write_bits(0xCD, 8)
        data = bw.flush()
        # Now read back
        br = BitReader(data)
        assert br.read_bits(8) == 0xAB
        assert br.read_bits(8) == 0xCD

    def test_exhausted(self):
        br = BitReader(b"\x01")
        assert not br.exhausted()
        br.read_bits(8)  # consume the full byte
        assert br.exhausted()

    def test_eof_raises(self):
        br = BitReader(b"")
        with pytest.raises(EOFError):
            br.read_bits(1)

    def test_tell(self):
        br = BitReader(b"\x01\x02")
        assert br.tell_bits() == 0
        assert br.tell_bytes() == 0
        br.read_bits(4)
        assert br.tell_bits() == 4
        assert br.tell_bytes() == 0
        br.read_bits(4)
        assert br.tell_bits() == 8
        assert br.tell_bytes() == 1


class TestRoundTrip:
    """BitWriter → BitReader round-trip."""

    def test_round_trip_bits(self):
        bw = BitWriter()
        values = [(0b0, 1), (0b10, 2), (0b110, 3), (0b111, 3), (0xFF, 8)]
        for v, n in values:
            bw.write_bits(v, n)
        data = bw.flush()

        br = BitReader(data)
        for v, n in values:
            assert br.read_bits(n) == v
