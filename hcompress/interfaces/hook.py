"""ICompressHook / IDecompressHook — lifecycle hook interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hcompress.format import HeaderInfo


# ── Pipeline context dataclasses ─────────────────────────────────────────────


@dataclass
class CompressContext:
    """
    Mutable context carried through the entire compression pipeline.

    Hooks and extensions can read / write this context; it is passed
    by reference, so modifications by one hook are visible to all
    subsequent hooks.
    """

    input_path: str = ""
    output_path: str = ""
    level: int = 6
    original_size: int = 0
    compressed_size: int = 0

    # Shared extension data dict — each IExtension reads/writes its
    # namespace keyed by extension_id so they don't step on each other.
    extension_data: dict = field(default_factory=dict)

    # If True, the pipeline will abort at the next safe checkpoint.
    abort: bool = False


@dataclass
class DecompressContext:
    """Mutable context carried through the decompression pipeline."""

    input_path: str = ""
    output_path: str = ""
    header: "HeaderInfo | None" = None
    extension_data: dict = field(default_factory=dict)
    abort: bool = False


# ── Compress hook ────────────────────────────────────────────────────────────


class ICompressHook(ABC):
    """
    Compression lifecycle hook.

    Hooks are called in registration order at each pipeline stage.
    They are purely for side-effects (logging, metrics, guard checks);
    they should NOT mutate data — use IExtension or ITransform for that.

    Implementations (future):
        - MetricsCollector  — record timing / ratio stats.
        - FileLogger        — write a compression log alongside the .hcf.
        - MalwareScanner    — scan input before compressing.
    """

    @abstractmethod
    def on_start(self, ctx: CompressContext) -> None:
        """Called before any I/O or computation begins."""
        ...

    @abstractmethod
    def on_freq_done(self, ctx: CompressContext, freq: list[int]) -> None:
        """Called after frequency table has been built."""
        ...

    @abstractmethod
    def on_header_written(self, ctx: CompressContext, header: "HeaderInfo") -> None:
        """Called after the HCF header has been written to disk."""
        ...

    @abstractmethod
    def on_block_encoded(
        self, ctx: CompressContext, block_idx: int, raw: bytes, encoded: bytes
    ) -> None:
        """Called after each block is encoded."""
        ...

    @abstractmethod
    def on_done(self, ctx: CompressContext, stats: "CompressStats") -> None:
        """Called on successful completion."""
        ...

    @abstractmethod
    def on_error(self, ctx: CompressContext, error: Exception) -> None:
        """Called if compression fails at any stage."""
        ...


# ── Decompress hook ──────────────────────────────────────────────────────────


class IDecompressHook(ABC):
    """
    Decompression lifecycle hook.

    Key use: the on_header_read hook is the designated extension point
    for compression-bomb detection.  The hook receives the full HeaderInfo
    (including original_size) *before* any decompressed byte is written,
    and can return False to abort.

    Implementations (future):
        - BombGuard         — reject files whose expansion ratio exceeds a threshold.
        - NestingDetector   — reject recursively compressed archives.
        - IntegrityVerifier — check header CRC / checksum before decoding.
    """

    @abstractmethod
    def on_start(self, ctx: DecompressContext) -> None:
        """Called before any I/O or computation begins."""
        ...

    @abstractmethod
    def on_header_read(self, ctx: DecompressContext, header: "HeaderInfo") -> bool:
        """
        Called immediately after parsing the HCF header, *before* any decoding.

        Returns:
            True to continue decompression, False to abort.
            This is the bomb-guard insertion point — inspect header.original_size
            vs the compressed file size and reject if the ratio is suspicious.
        """
        ...

    @abstractmethod
    def on_block_decoded(
        self, ctx: DecompressContext, block_idx: int, encoded: bytes, raw: bytes
    ) -> None:
        """Called after each block is decoded."""
        ...

    @abstractmethod
    def on_done(self, ctx: DecompressContext, stats: "DecompressStats") -> None:
        """Called on successful completion."""
        ...

    @abstractmethod
    def on_error(self, ctx: DecompressContext, error: Exception) -> None:
        """Called if decompression fails at any stage."""
        ...
