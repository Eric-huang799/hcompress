"""BombGuard — compression-bomb detection plugin.

Implements IDecompressHook.  Inspects the HCF header *before* any
decompressed byte is written and aborts if the expansion ratio
exceeds a configurable threshold.

A compression bomb is a tiny archive that expands to a gigantic
output, designed to exhaust disk / memory.  Because the HCF header
stores the original file size, we can detect this with zero I/O
overhead — just compare the numbers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hcompress.interfaces.hook import IDecompressHook

if TYPE_CHECKING:
    from hcompress.interfaces.hook import DecompressContext
    from hcompress.format import HeaderInfo


class BombDetectedError(RuntimeError):
    """Raised when a suspected compression bomb is detected."""


class BombGuardPlugin(IDecompressHook):
    """Reject files whose expansion ratio exceeds *max_ratio*.

    Default threshold is **100:1** — i.e. if the compressed file is
    1 KB but claims to decompress to more than 100 KB, decompression
    is aborted.

    Also enforces a *max_recursion_depth* to catch nested archives
    (a .hcf inside a .hcf inside a .hcf …).  This is a soft limit
    tracked per-process via a class-level counter.

    Configuration
    -------------
    >>> guard = BombGuardPlugin(max_ratio=100, max_depth=5)
    >>> config = DecompressConfig(hooks=[guard])

    Disable via CLI
    ---------------
    ``hcompress d file.hcf --no-bomb-guard``  (removes the hook).
    """

    # Per-process recursion counter (class-level — crude but effective)
    _depth: int = 0

    def __init__(self, max_ratio: int = 100, max_depth: int = 5) -> None:
        self.max_ratio = max_ratio
        self.max_depth = max_depth

    # ── IDecompressHook ────────────────────────────────────────────────

    def on_start(self, ctx: DecompressContext) -> None:
        BombGuardPlugin._depth += 1
        if BombGuardPlugin._depth > self.max_depth:
            BombGuardPlugin._depth -= 1
            raise BombDetectedError(
                f"递归嵌套深度 {BombGuardPlugin._depth} 超过上限 {self.max_depth}。"
                f"可能是嵌套压缩炸弹。"
            )

    def on_header_read(self, ctx: DecompressContext, header: HeaderInfo) -> bool:
        # Compute expansion ratio
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
        return True  # allow decompression to continue

    def on_block_decoded(
        self, ctx: DecompressContext, block_idx: int, encoded: bytes, raw: bytes
    ) -> None:
        pass  # nothing to check per-block

    def on_done(self, ctx: DecompressContext, stats) -> None:
        BombGuardPlugin._depth = max(0, BombGuardPlugin._depth - 1)

    def on_error(self, ctx: DecompressContext, error: Exception) -> None:
        BombGuardPlugin._depth = max(0, BombGuardPlugin._depth - 1)
