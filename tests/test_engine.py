"""Tests for engine.py — compress / decompress round-trip."""

import os
import tempfile
import pytest
from hcompress.engine import (
    CompressConfig,
    DecompressConfig,
    CompressStats,
    DecompressStats,
    compress,
    decompress,
)
from hcompress.format import read_header


class TestCompressDecompress:
    """End-to-end round-trip tests."""

    def _round_trip(self, data: bytes) -> DecompressStats:
        with tempfile.NamedTemporaryFile(suffix=".hcf", delete=False) as tmp_hcf:
            hcf_path = tmp_hcf.name
        with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tmp_out:
            out_path = tmp_out.name
        in_path = out_path + ".in"

        try:
            with open(in_path, "wb") as f:
                f.write(data)

            c_stats = compress(in_path, hcf_path)
            assert isinstance(c_stats, CompressStats)
            assert c_stats.original_size == len(data)

            d_stats = decompress(hcf_path, out_path)
            assert isinstance(d_stats, DecompressStats)
            assert d_stats.checksum_ok
            assert d_stats.original_size == len(data)

            with open(out_path, "rb") as f:
                restored = f.read()
            assert restored == data
            return d_stats
        finally:
            for p in (hcf_path, out_path, in_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def test_empty(self):
        self._round_trip(b"")

    def test_single_byte(self):
        self._round_trip(b"X")

    def test_repeated_text(self):
        self._round_trip(b"hello world " * 1000)

    def test_all_bytes(self):
        self._round_trip(bytes(range(256)) * 50)

    def test_random_binary(self):
        import random
        random.seed(12345)
        data = bytes(random.randint(0, 255) for _ in range(10000))
        self._round_trip(data)

    def test_single_char_repeated(self):
        """Highly compressible: 10000 identical bytes."""
        self._round_trip(b"A" * 10000)


class TestConfig:
    def test_compress_config_defaults(self):
        cfg = CompressConfig()
        assert cfg.level == 6
        assert cfg.entropy_coder is None
        assert cfg.transforms == []
        assert cfg.extensions == []

    def test_decompress_config_defaults(self):
        cfg = DecompressConfig()
        assert cfg.checksum is None
        assert cfg.extensions == []

    def test_custom_level(self):
        cfg = CompressConfig(level=9)
        assert cfg.level == 9


class TestHeaderExtensionData:
    """Verify extension data round-trips through HCF header."""

    def test_extension_json_round_trip(self):
        from hcompress.interfaces.extension import IExtension
        from hcompress.interfaces.hook import CompressContext, DecompressContext

        class DummyExt(IExtension):
            extension_id = "test.dummy"
            version = "1.0"

            def on_compress_start(self, ctx):
                pass

            def on_compress_data(self, ctx, data, stage):
                return data

            def on_compress_done(self, ctx, stats):
                pass

            def on_decompress_start(self, ctx):
                pass

            def on_decompress_data(self, ctx, data, stage):
                return data

            def on_decompress_done(self, ctx, stats):
                pass

            def on_error(self, ctx, error):
                pass

            def get_extension_data(self):
                return {"key": "value"}

            def set_extension_data(self, data):
                pass

        ext = DummyExt()
        cfg = CompressConfig(extensions=[ext])
        data = b"test extension data"

        with tempfile.NamedTemporaryFile(suffix=".hcf", delete=False) as tmp_hcf:
            hcf_path = tmp_hcf.name
        out_path = hcf_path + ".out"

        try:
            with open(hcf_path + ".in", "wb") as f:
                f.write(data)

            compress(hcf_path + ".in", hcf_path, cfg)

            with open(hcf_path, "rb") as f:
                header = read_header(f)
            assert header.has_extension
            assert header.extension_data
            assert b"test.dummy" in header.extension_data
        finally:
            for p in (hcf_path, hcf_path + ".in", out_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
