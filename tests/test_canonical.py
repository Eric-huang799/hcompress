"""Tests for canonical.py — Huffman codec."""

import pytest
from hcompress.canonical import (
    freq_table,
    canonical_from_freq,
    build_decode_table,
    decode_symbol,
    encode_data,
)
from hcompress.bitstream import BitWriter, BitReader


class TestFreqTable:
    def test_empty(self):
        assert freq_table(b"") == [0] * 256

    def test_single_byte(self):
        f = freq_table(b"A")
        assert f[ord("A")] == 1
        assert sum(f) == 1

    def test_multiple(self):
        f = freq_table(b"hello")
        assert f[ord("h")] == 1
        assert f[ord("e")] == 1
        assert f[ord("l")] == 2
        assert f[ord("o")] == 1


class TestCanonicalCodes:
    def test_empty_input(self):
        codes, bl = canonical_from_freq([0] * 256)
        assert all(b == 0 for b in bl)
        assert all(c == 0 for c in codes)

    def test_single_symbol(self):
        f = [0] * 256
        f[ord("A")] = 100
        codes, bl = canonical_from_freq(f)
        assert bl[ord("A")] == 1
        assert codes[ord("A")] == 0

    def test_two_symbols(self):
        f = [0] * 256
        f[ord("A")] = 50
        f[ord("B")] = 50
        codes, bl = canonical_from_freq(f)
        # Equal frequencies — both get length 1
        assert bl[ord("A")] == 1
        assert bl[ord("B")] == 1
        assert codes[ord("A")] != codes[ord("B")]

    def test_canonical_property(self):
        """Codes with same length should be consecutive, smaller symbol → smaller code."""
        data = b"aaabbc"
        f = freq_table(data)
        codes, bl = canonical_from_freq(f)

        # Group by length
        by_len = {}
        for sym in range(256):
            if bl[sym] > 0:
                by_len.setdefault(bl[sym], []).append((codes[sym], sym))

        for length, pairs in by_len.items():
            pairs.sort()  # by code
            codes_only = [c for c, _ in pairs]
            assert codes_only == list(range(codes_only[0], codes_only[-1] + 1))


class TestDecodeTable:
    def test_round_trip_small(self):
        data = b"hello world hello huffman"
        f = freq_table(data)
        codes, bl = canonical_from_freq(f)
        base_code, offset, syms_by_len, max_len = build_decode_table(bl)

        writer = BitWriter()
        encode_data(writer, data, codes, bl)
        encoded = writer.flush()

        reader = BitReader(encoded)
        decoded = bytearray()
        for _ in range(len(data)):
            sym = decode_symbol(reader, base_code, offset, syms_by_len, max_len)
            decoded.append(sym)

        assert bytes(decoded) == data

    def test_round_trip_binary(self):
        data = bytes(range(256)) * 10
        f = freq_table(data)
        codes, bl = canonical_from_freq(f)
        base_code, offset, syms_by_len, max_len = build_decode_table(bl)

        writer = BitWriter()
        encode_data(writer, data, codes, bl)
        encoded = writer.flush()

        reader = BitReader(encoded)
        decoded = bytearray()
        for _ in range(len(data)):
            sym = decode_symbol(reader, base_code, offset, syms_by_len, max_len)
            decoded.append(sym)

        assert bytes(decoded) == data

    def test_missing_symbol_raises(self):
        data = b"aaaa"
        f = freq_table(data)
        codes, bl = canonical_from_freq(f)

        writer = BitWriter()
        # Encode a 'b' which has no code
        with pytest.raises(ValueError):
            encode_data(writer, b"b", codes, bl)
