"""IHook — unified lifecycle hook interface.

Merges the former ICompressHook and IDecompressHook into a single ABC.
Plugins set ``hook_id`` to declare which side(s) they handle:
    0 = both, 1 = compress only, 2 = decompress only.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hcompress.format import HeaderInfo


# ── Pipeline context dataclasses ─────────────────────────────────────────────

@dataclass
class CompressContext:
    """Mutable context carried through the entire compression pipeline."""

    input_path: str = ""
    output_path: str = ""
    level: int = 6
    original_size: int = 0
    compressed_size: int = 0
    extension_data: dict = field(default_factory=dict)
    abort: bool = False
    _parallel_enabled: bool = False
    _parallel_workers: int = 4


@dataclass
class DecompressContext:
    """Mutable context carried through the decompression pipeline."""

    input_path: str = ""
    output_path: str = ""
    header: "HeaderInfo | None" = None
    extension_data: dict = field(default_factory=dict)
    abort: bool = False


# ── Unified hook ─────────────────────────────────────────────────────────────

class IHook(ABC):
    """Lifecycle hook for both compression and decompression.

    Set ``hook_id`` on the class to declare which side(s) the plugin
    handles:
        - hook_id = 0: both sides (default)
        - hook_id = 1: compress only
        - hook_id = 2: decompress only

    The PluginRegistry uses hook_id to decide whether to place the
    instance in compress_hooks, decompress_hooks, or both.
    """

    hook_id: int = 0  # 0 = both, 1 = compress only, 2 = decompress only

    # ── compress side ─────────────────────────────────────────────────

    @abstractmethod
    def on_compress_start(self, ctx: CompressContext) -> None:
        """Called before any I/O or computation begins on compress."""

    @abstractmethod
    def on_freq_done(self, ctx: CompressContext, freq: list[int]) -> None:
        """Called after frequency table has been built."""

    @abstractmethod
    def on_header_written(self, ctx: CompressContext, header: "HeaderInfo") -> None:
        """Called after the HCF header has been written to disk."""

    @abstractmethod
    def on_block_encoded(
        self, ctx: CompressContext, block_idx: int, raw: bytes, encoded: bytes
    ) -> None:
        """Called after each block is encoded."""

    @abstractmethod
    def on_compress_done(self, ctx: CompressContext, stats) -> None:
        """Called on successful compression completion."""

    # ── decompress side ──────────────────────────────────────────────

    @abstractmethod
    def on_decompress_start(self, ctx: DecompressContext) -> None:
        """Called before any I/O or computation begins on decompress."""

    @abstractmethod
    def on_header_read(self, ctx: DecompressContext, header: "HeaderInfo") -> bool:
        """Called after HCF header is parsed, before any decoding.

        Return True to continue, False to abort.  This is the bomb-guard
        insertion point.
        """

    @abstractmethod
    def on_block_decoded(
        self, ctx: DecompressContext, block_idx: int, encoded: bytes, raw: bytes
    ) -> None:
        """Called after each block is decoded."""

    @abstractmethod
    def on_decompress_done(self, ctx: DecompressContext, stats) -> None:
        """Called on successful decompression completion."""

    # ── shared ───────────────────────────────────────────────────────

    @abstractmethod
    def on_error(self, ctx: "CompressContext | DecompressContext", error: Exception) -> None:
        """Called if the pipeline fails at any stage."""
