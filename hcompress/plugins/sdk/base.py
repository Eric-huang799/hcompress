"""No-op base classes for every hcompress interface.

Subclass these instead of the raw ABCs — override only the methods you need.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from hcompress.interfaces.codec import IEntropyCodec
from hcompress.interfaces.transform import ITransform
from hcompress.interfaces.filter import IFilter
from hcompress.interfaces.matchfinder import IMatchFinder
from hcompress.interfaces.checksum import IChecksum
from hcompress.interfaces.io_backend import IIOBackend
from hcompress.interfaces.block_splitter import IBlockSplitter
from hcompress.interfaces.hook import IHook
from hcompress.interfaces.observer import IObserver
from hcompress.interfaces.extension import IExtension
from hcompress.plugins.manifest import PluginMeta

if TYPE_CHECKING:
    from hcompress.interfaces.hook import CompressContext, DecompressContext
    from hcompress.format import HeaderInfo


# ── Codec ───────────────────────────────────────────────────────────────────

class BaseCodec(IEntropyCodec):
    codec_id: int = 0
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-codec", plugin_type="codec",
    )

    def encode(self, data: bytes, freq: list[int]) -> tuple[bytes, list[int]]:
        raise NotImplementedError("encode must be implemented")

    def decode(self, bitstream, bit_lengths: list[int], original_size: int) -> bytes:
        raise NotImplementedError("decode must be implemented")


# ── Transform ───────────────────────────────────────────────────────────────

class BaseTransform(ITransform):
    name: str = "unnamed"
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-transform", plugin_type="transform",
    )

    def forward(self, data: bytes) -> bytes:
        return data

    def reverse(self, data: bytes) -> bytes:
        return data


# ── Filter ──────────────────────────────────────────────────────────────────

class BaseFilter(IFilter):
    filter_id: int = 0
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-filter", plugin_type="filter",
    )

    def apply(self, data: bytes) -> bytes:
        return data

    def revert(self, data: bytes) -> bytes:
        return data


# ── MatchFinder ─────────────────────────────────────────────────────────────

class BaseMatchFinder(IMatchFinder):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-matchfinder", plugin_type="matchfinder",
    )

    @property
    def window_size(self) -> int:
        return 32768

    def find_matches(self, data: bytes, pos: int) -> list:
        return []


# ── Checksum ────────────────────────────────────────────────────────────────

class BaseChecksum(IChecksum):
    checksum_id: int = 255
    digest_size: int = 0
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-checksum", plugin_type="checksum",
    )

    def compute(self, data: bytes) -> bytes:
        raise NotImplementedError("compute must be implemented")

    def verify(self, data: bytes, expected: bytes) -> bool:
        return self.compute(data) == expected


# ── IO Backend ──────────────────────────────────────────────────────────────

class BaseIOBackend(IIOBackend):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-io", plugin_type="io",
    )

    def open_read(self, path: str):
        return open(path, "rb")

    def open_write(self, path: str):
        return open(path, "wb")

    def source_size(self, source) -> int:
        import os
        if isinstance(source, str):
            return os.path.getsize(source)
        try:
            pos = source.tell()
            source.seek(0, 2)
            size = source.tell()
            source.seek(pos)
            return size
        except Exception:
            return -1


# ── Block Splitter ──────────────────────────────────────────────────────────

class BaseBlockSplitter(IBlockSplitter):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-splitter", plugin_type="block_splitter",
    )

    def split(self, data: bytes) -> list:
        from hcompress.interfaces.block_splitter import Block
        return [Block(offset=0, data=data, index=0)]

    def merge(self, blocks: list) -> bytes:
        blocks.sort(key=lambda b: b.index)
        return b"".join(b.data for b in blocks)


# ── Hook (no-op defaults, both sides) ───────────────────────────────────────

class BaseHook(IHook):
    hook_id: int = 0
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-hook", plugin_type="hook",
    )

    def on_compress_start(self, ctx: CompressContext) -> None: pass
    def on_freq_done(self, ctx: CompressContext, freq: list[int]) -> None: pass
    def on_header_written(self, ctx: CompressContext, header: HeaderInfo) -> None: pass
    def on_block_encoded(self, ctx: CompressContext, block_idx: int,
                         raw: bytes, encoded: bytes) -> None: pass
    def on_compress_done(self, ctx: CompressContext, stats) -> None: pass
    def on_decompress_start(self, ctx: DecompressContext) -> None: pass
    def on_header_read(self, ctx: DecompressContext, header: HeaderInfo) -> bool:
        return True
    def on_block_decoded(self, ctx: DecompressContext, block_idx: int,
                         encoded: bytes, raw: bytes) -> None: pass
    def on_decompress_done(self, ctx: DecompressContext, stats) -> None: pass
    def on_error(self, ctx, error: Exception) -> None: pass


# ── Observer (no-op defaults) ───────────────────────────────────────────────

class BaseObserver(IObserver):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-observer", plugin_type="observer",
    )

    def on_progress(self, current: int, total: int, phase: str) -> None: pass
    def on_event(self, event) -> None: pass


# ── Extension (no-op defaults) ──────────────────────────────────────────────

class BaseExtension(IExtension):
    extension_id: str = "com.example.unnamed"
    version: str = "0.1.0"
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="unnamed-extension", plugin_type="extension",
    )

    def on_compress_start(self, ctx: CompressContext) -> None: pass
    def on_compress_data(self, ctx: CompressContext, data: bytes, stage: str) -> bytes:
        return data
    def on_compress_done(self, ctx: CompressContext, stats) -> None: pass
    def on_decompress_start(self, ctx: DecompressContext) -> None: pass
    def on_decompress_data(self, ctx: DecompressContext, data: bytes, stage: str) -> bytes:
        return data
    def on_decompress_done(self, ctx: DecompressContext, stats) -> None: pass
    def on_error(self, ctx, error: Exception) -> None: pass
    def get_extension_data(self) -> dict:
        return {}
    def set_extension_data(self, data: dict) -> None: pass
