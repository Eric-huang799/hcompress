"""Tests for format.py — HCF header read/write."""

import io
import pytest
from hcompress.format import (
    MAGIC,
    HeaderInfo,
    write_header,
    read_header,
    FLAG_HAS_EXTENSION,
)


def _make_bit_lengths() -> list[int]:
    """Dummy bit-lengths for testing."""
    bl = [0] * 256
    bl[ord("a")] = 1
    bl[ord("b")] = 2
    bl[ord("c")] = 2
    return bl


class TestWriteRead:
    def test_basic_header(self):
        buf = io.BytesIO()
        bl = _make_bit_lengths()
        write_header(buf, bl, original_size=100)
        buf.seek(0)
        h = read_header(buf)
        assert h.version == 1
        assert h.original_size == 100
        assert h.bit_lengths[ord("a")] == 1
        assert h.bit_lengths[ord("b")] == 2
        assert h.has_extension is False

    def test_with_extension(self):
        buf = io.BytesIO()
        bl = _make_bit_lengths()
        ext = b'{"hello":"world"}'
        write_header(buf, bl, original_size=500, flags=FLAG_HAS_EXTENSION, extension_data=ext)
        buf.seek(0)
        h = read_header(buf)
        assert h.original_size == 500
        assert h.has_extension is True
        assert h.extension_data == ext

    def test_bad_magic(self):
        buf = io.BytesIO(b"BADMAGIC" + b"\x00" * 268)
        with pytest.raises(ValueError, match="Bad magic"):
            read_header(buf)

    def test_truncated(self):
        buf = io.BytesIO(b"short")
        with pytest.raises(EOFError):
            read_header(buf)


class TestHeaderInfo:
    def test_level_from_flags(self):
        h = HeaderInfo(version=1, flags=0x000C, bit_lengths=[0]*256, original_size=0)
        # flags=0x0C → bits 1-4: 0110 = 6
        assert h.compression_level == 6

    def test_coder_id(self):
        h = HeaderInfo(version=1, flags=0, bit_lengths=[0]*256, original_size=0)
        assert h.coder_id == 0
