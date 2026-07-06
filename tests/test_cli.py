"""Tests for cli.py — Click CLI commands."""

import os
import tempfile
import pytest
from click.testing import CliRunner
from hcompress.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_file():
    """Create a small test file, yield path, clean up after."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.write(fd, b"hello world hello huffman " * 100)
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


class TestCompressCommand:
    def test_compress_default_output(self, runner, sample_file):
        result = runner.invoke(main, ["c", sample_file])
        # Default output appends .hcf (e.g. foo.txt → foo.txt.hcf)
        hcf = sample_file + ".hcf"
        assert os.path.exists(hcf), f"Expected {hcf} to exist"
        os.unlink(hcf)

    def test_compress_explicit_output(self, runner, sample_file):
        out = sample_file + ".custom.hcf"
        result = runner.invoke(main, ["c", sample_file, "-o", out, "-f"])
        assert os.path.exists(out)
        os.unlink(out)

    def test_compress_no_overwrite(self, runner, sample_file):
        out = sample_file + ".exists.hcf"
        with open(out, "w") as f:
            f.write("exists")
        result = runner.invoke(main, ["c", sample_file, "-o", out])
        # Should fail because file exists
        # (exit code may be 0 or 1 depending on how click handles SystemExit)
        # but the output file should still contain "exists"
        with open(out) as f:
            assert f.read() == "exists"
        os.unlink(out)

    def test_compress_force_overwrite(self, runner, sample_file):
        out = sample_file + ".force.hcf"
        with open(out, "w") as f:
            f.write("exists")
        result = runner.invoke(main, ["c", sample_file, "-o", out, "-f"])
        # Should succeed
        with open(out, "rb") as f:
            magic = f.read(4)
        assert magic == b"HCF\x1a"
        os.unlink(out)

    def test_compress_nonexistent_file(self, runner):
        result = runner.invoke(main, ["c", "/nonexistent/file.txt"])
        assert result.exit_code != 0


class TestDecompressCommand:
    def test_decompress_round_trip(self, runner, sample_file):
        hcf = sample_file + ".hcf"
        out = sample_file + ".restored"
        try:
            # Compress first
            r1 = runner.invoke(main, ["c", sample_file, "-o", hcf])
            assert os.path.exists(hcf)

            # Decompress
            r2 = runner.invoke(main, ["d", hcf, "-o", out])
            assert os.path.exists(out)

            # Compare
            with open(sample_file, "rb") as f:
                orig = f.read()
            with open(out, "rb") as f:
                restored = f.read()
            assert orig == restored
        finally:
            for p in (hcf, out):
                try:
                    os.unlink(p)
                except OSError:
                    pass


class TestInfoCommand:
    def test_info(self, runner, sample_file):
        hcf = sample_file + ".hcf"
        runner.invoke(main, ["c", sample_file, "-o", hcf])
        try:
            result = runner.invoke(main, ["info", hcf])
            assert "Original size" in result.output
        finally:
            try:
                os.unlink(hcf)
            except OSError:
                pass

    def test_info_bad_file(self, runner):
        result = runner.invoke(main, ["info", "/nonexistent.hcf"])
        assert result.exit_code != 0


class TestBenchCommand:
    def test_bench(self, runner, sample_file):
        result = runner.invoke(main, ["bench", sample_file, "-n", "2"])
        assert "Benchmark" in result.output


class TestVersion:
    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert "hcompress" in result.output
