"""
hcompress — High-performance Canonical Huffman compression tool.

Usage:
    python -m hcompress c <file> [-o <out>] [--level <0-9>]
    python -m hcompress d <file> [-o <out>]
    python -m hcompress info <file>
    python -m hcompress bench <file> [-n <iters>]
"""

__version__ = "0.1.2"
__all__ = [
    "__version__",
    "compress",
    "decompress",
    "CompressConfig",
    "DecompressConfig",
    "CompressStats",
    "DecompressStats",
]
