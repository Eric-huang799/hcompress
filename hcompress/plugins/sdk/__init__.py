"""
Plugin SDK — quick-start helpers for building hcompress plugins.

Usage:
    from hcompress.plugins.sdk import BaseDecompressHook

    class MyBombGuard(BaseDecompressHook):
        def on_header_read(self, ctx, header):
            if header.original_size > 1_000_000:
                raise RuntimeError("Suspicious!")
            return True

All abstract methods default to no-ops — override only what you need.
"""

from hcompress.plugins.sdk.base import (
    BaseCodec,
    BaseTransform,
    BaseFilter,
    BaseMatchFinder,
    BaseChecksum,
    BaseIOBackend,
    BaseBlockSplitter,
    BaseCompressHook,
    BaseDecompressHook,
    BaseObserver,
    BaseExtension,
)
from hcompress.plugins.sdk.scaffold import scaffold

__all__ = [
    "BaseCodec", "BaseTransform", "BaseFilter",
    "BaseMatchFinder", "BaseChecksum", "BaseIOBackend",
    "BaseBlockSplitter", "BaseCompressHook", "BaseDecompressHook",
    "BaseObserver", "BaseExtension",
    "scaffold",
]
