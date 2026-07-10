"""BombGuard — compression-bomb detection plugin (decompress only)."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from hcompress.interfaces.hook import IHook
from hcompress.plugins.manifest import PluginMeta

if TYPE_CHECKING:
    from hcompress.interfaces.hook import DecompressContext
    from hcompress.format import HeaderInfo


class BombDetectedError(RuntimeError):
    pass


class BombGuardPlugin(IHook):
    hook_id: int = 2  # decompress only

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="BombGuardPlugin", version="1.0.0", author="hcompress team",
        description="压缩炸弹/嵌套炸弹检测，默认 100:1 膨胀比阈值",
        plugin_type="hook", priority=10,
    )

    _depth: int = 0

    def __init__(self, max_ratio: int = 100, max_depth: int = 5) -> None:
        self.max_ratio = max_ratio
        self.max_depth = max_depth

    def on_compress_start(self, ctx): pass
    def on_freq_done(self, ctx, freq): pass
    def on_header_written(self, ctx, header): pass
    def on_block_encoded(self, ctx, block_idx, raw, encoded): pass
    def on_compress_done(self, ctx, stats): pass

    def on_decompress_start(self, ctx):
        BombGuardPlugin._depth += 1
        if BombGuardPlugin._depth > self.max_depth:
            BombGuardPlugin._depth -= 1
            raise BombDetectedError(
                f"递归嵌套深度 {BombGuardPlugin._depth} 超过上限 {self.max_depth}。"
                f"可能是嵌套压缩炸弹。"
            )

    def on_header_read(self, ctx: DecompressContext, header: HeaderInfo) -> bool:
        import os
        compressed_size = os.path.getsize(ctx.input_path) if ctx.input_path else 1
        if compressed_size <= 0:
            compressed_size = 1
        ratio = header.original_size / compressed_size
        if ratio > self.max_ratio:
            raise BombDetectedError(
                f"检测到疑似压缩炸弹！\n"
                f"  压缩文件: {compressed_size:,} 字节\n"
                f"  声称原始: {header.original_size:,} 字节\n"
                f"  膨胀比:   {ratio:.0f}:1  (阈值 {self.max_ratio}:1)\n"
                f"  请检查文件来源或使用 --no-bomb-guard 强制解压。"
            )
        return True

    def on_block_decoded(self, ctx, block_idx, encoded, raw): pass
    def on_decompress_done(self, ctx, stats):
        BombGuardPlugin._depth = max(0, BombGuardPlugin._depth - 1)

    def on_error(self, ctx, error):
        BombGuardPlugin._depth = max(0, BombGuardPlugin._depth - 1)
