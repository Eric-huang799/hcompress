"""Format handlers — decompress common archive formats.

Python stdlib already ships with gzip, bz2, lzma, zipfile, tarfile.
This module registers them as format plugins callable from hcompress.
"""

from __future__ import annotations

import gzip
import lzma
import os
import tarfile
import zipfile
from pathlib import Path

# ── Format detector ─────────────────────────────────────────────────────────

# Magic bytes → (name, handler function)
_FORMATS: dict[bytes, tuple[str, callable]] = {}


def register(magic: bytes, name: str, handler: callable) -> None:
    """Register a format handler keyed by file magic bytes."""
    _FORMATS[magic] = (name, handler)


def detect(filepath: str) -> str | None:
    """Return the format name if *filepath* is a known archive format."""
    try:
        with open(filepath, "rb") as f:
            head = f.read(8)
    except OSError:
        return None
    for magic, (name, _) in _FORMATS.items():
        if head.startswith(magic):
            return name
    return None


def decompress(filepath: str, output_dir: str) -> bool:
    """Decompress *filepath* using the appropriate format handler.

    Returns True on success, False if format not recognised.
    """
    os.makedirs(output_dir, exist_ok=True)
    try:
        with open(filepath, "rb") as f:
            head = f.read(8)
    except OSError:
        return False
    for magic, (name, handler) in _FORMATS.items():
        if head.startswith(magic):
            handler(filepath, output_dir)
            return True
    return False


# ── Gzip (.gz) ──────────────────────────────────────────────────────────────

def _decompress_gz(filepath: str, output_dir: str) -> None:
    out_name = os.path.basename(filepath).removesuffix(".gz")
    out_path = os.path.join(output_dir, out_name)
    with gzip.open(filepath, "rb") as f_in:
        with open(out_path, "wb") as f_out:
            f_out.write(f_in.read())


register(b"\x1f\x8b", "gzip", _decompress_gz)

# ── XZ / LZMA (.xz) ─────────────────────────────────────────────────────────

def _decompress_xz(filepath: str, output_dir: str) -> None:
    out_name = os.path.basename(filepath).removesuffix(".xz")
    out_path = os.path.join(output_dir, out_name)
    with lzma.open(filepath, "rb") as f_in:
        with open(out_path, "wb") as f_out:
            f_out.write(f_in.read())


register(b"\xfd7zXZ", "xz", _decompress_xz)

# ── ZIP (.zip) ──────────────────────────────────────────────────────────────

def _decompress_zip(filepath: str, output_dir: str) -> None:
    with zipfile.ZipFile(filepath, "r") as zf:
        zf.extractall(output_dir)


register(b"PK\x03\x04", "zip", _decompress_zip)
register(b"PK\x05\x06", "zip (empty)", _decompress_zip)

# ── TAR / TAR.GZ / TAR.BZ2 / TAR.XZ ─────────────────────────────────────────

def _decompress_tar(filepath: str, output_dir: str) -> None:
    with tarfile.open(filepath, "r:*") as tf:
        tf.extractall(output_dir)


register(b"ustar\x00", "tar", _decompress_tar)
register(b"ustar  \x00", "tar (GNU)", _decompress_tar)

# ── BZ2 (.bz2) ──────────────────────────────────────────────────────────────

def _decompress_bz2(filepath: str, output_dir: str) -> None:
    import bz2
    out_name = os.path.basename(filepath).removesuffix(".bz2")
    out_path = os.path.join(output_dir, out_name)
    with bz2.open(filepath, "rb") as f_in:
        with open(out_path, "wb") as f_out:
            f_out.write(f_in.read())


register(b"BZh", "bzip2", _decompress_bz2)

# ── 7z (.7z) ────────────────────────────────────────────────────────────────

def _decompress_7z(filepath: str, output_dir: str) -> None:
    import py7zr
    with py7zr.SevenZipFile(filepath, "r") as zf:
        zf.extractall(output_dir)


register(b"7z\xbc\xaf\x27\x1c", "7z", _decompress_7z)

# ── RAR (.rar) ──────────────────────────────────────────────────────────────

def _decompress_rar(filepath: str, output_dir: str) -> None:
    import rarfile
    with rarfile.RarFile(filepath, "r") as rf:
        rf.extractall(output_dir)


register(b"Rar!\x1a\x07\x00", "rar (v1.5)", _decompress_rar)
register(b"Rar!\x1a\x07\x01\x00", "rar (v5)", _decompress_rar)

# ── Zstd (.zst / .zstd) ─────────────────────────────────────────────────────

def _decompress_zstd(filepath: str, output_dir: str) -> None:
    import zstandard as zstd
    out_name = os.path.basename(filepath)
    for ext in (".zst", ".zstd"):
        if out_name.endswith(ext):
            out_name = out_name[:-len(ext)]
            break
    out_path = os.path.join(output_dir, out_name)
    with open(filepath, "rb") as f_in:
        dctx = zstd.ZstdDecompressor()
        with open(out_path, "wb") as f_out:
            dctx.copy_stream(f_in, f_out)


register(b"\x28\xb5\x2f\xfd", "zstd", _decompress_zstd)

# ── Brotli (.br) ────────────────────────────────────────────────────────────

def _decompress_brotli(filepath: str, output_dir: str) -> None:
    import brotli
    out_name = os.path.basename(filepath).removesuffix(".br")
    out_path = os.path.join(output_dir, out_name)
    with open(filepath, "rb") as f_in:
        data = brotli.decompress(f_in.read())
    with open(out_path, "wb") as f_out:
        f_out.write(data)


register(b"\xce\xb2\xcf\x81", "brotli", _decompress_brotli)

# ── LZ4 (.lz4) ──────────────────────────────────────────────────────────────

def _decompress_lz4(filepath: str, output_dir: str) -> None:
    import lz4.frame
    out_name = os.path.basename(filepath).removesuffix(".lz4")
    out_path = os.path.join(output_dir, out_name)
    with open(filepath, "rb") as f_in:
        data = lz4.frame.decompress(f_in.read())
    with open(out_path, "wb") as f_out:
        f_out.write(data)


register(b"\x04\x22\x4d\x18", "lz4", _decompress_lz4)

# ── Info ────────────────────────────────────────────────────────────────────

def supported_formats() -> list[str]:
    """Return names of all registered decompression formats."""
    return sorted(set(name for _, (name, _) in _FORMATS.items()))
