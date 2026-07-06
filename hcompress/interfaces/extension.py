"""IExtension — universal custom extension interface.

This is the escape hatch for anything the predefined interfaces don't cover.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hcompress.interfaces.hook import CompressContext, DecompressContext


class IExtension(ABC):
    """
    Universal custom extension — the escape hatch for unanticipated needs.

    Design intent
    -------------
    The 8 predefined interfaces (IEntropyCodec, ITransform, IFilter, ...)
    cover known extension dimensions.  IExtension is the catch-all for
    requirements nobody thought of yet.

    Each IExtension implementation:
    - Has a unique ``extension_id`` (reverse-DNS style recommended).
    - Can hook into both compress and decompress pipelines at multiple
      stages via the ``stage`` parameter of ``on_*_data``.
    - Persists custom data into the HCF header extension JSON through
      ``get_extension_data()`` / ``set_extension_data()``.

    The HCF header stores a JSON dict keyed by ``extension_id``, so
    multiple extensions can coexist without conflict.

    Example use cases
    -----------------
    - **AES encryption**:  encrypt in ``post_encode`` stage, decrypt
      in ``raw_header`` stage; store IV/salt in extension_data.
    - **Digital signature**: sign the bitstream in ``pre_write`` stage,
      verify in ``raw_header`` stage.
    - **Metadata injection**: write author / timestamp / copyright into
      extension_data during compression; read back on decompression.
    - **Content classifier**: run a fast ML model on the decoded output
      in ``post_decode`` stage; emit tags into extension_data so the
      next tool in a pipeline knows what the file is without sniffing it.
    - **AI pre-analysis**: use a small model to predict the optimal
      block-splitter parameters for this specific file, store the
      recommendation in extension_data.
    - **Multi-volume archiving**: split the bitstream across multiple
      files in ``pre_write``; reassemble in ``raw_header``.
    - **Remote transfer adapter**: on compress, POST the .hcf to a
      cloud bucket immediately after ``pre_write``; on decompress,
      fetch from a URL in ``raw_header``.
    - **Custom compression-level policy**: inspect the file extension
      or magic bytes at ``raw`` stage and override ctx.level.

    Lifecycle (compress)
    --------------------
    1. on_compress_start(ctx)
    2. on_compress_data(ctx, raw_data, stage='raw')
    3. on_compress_data(ctx, freq, stage='post_freq')
    4. on_compress_data(ctx, bitstream, stage='post_encode')
    5. on_compress_data(ctx, bitstream, stage='pre_write')
    6. on_compress_done(ctx, stats)
    (on_error at any stage if something throws)

    Lifecycle (decompress)
    ----------------------
    1. on_decompress_start(ctx)
    2. on_decompress_data(ctx, header_bytes, stage='raw_header')
    3. on_decompress_data(ctx, decoded_data, stage='post_decode')
    4. on_decompress_data(ctx, decoded_data, stage='pre_write')
    5. on_decompress_done(ctx, stats)
    (on_error at any stage if something throws)
    """

    # ── Identity ─────────────────────────────────────────────────────────

    extension_id: str   # e.g. "com.eric.aes-encrypt"
    version: str        # semantic version, e.g. "1.0.0"

    # ── Compress side ────────────────────────────────────────────────────

    @abstractmethod
    def on_compress_start(self, ctx: "CompressContext") -> None:
        """Called before any work begins.

        Use this for one-time setup: derive keys, open network
        connections, validate prerequisites, etc.
        """
        ...

    @abstractmethod
    def on_compress_data(
        self, ctx: "CompressContext", data: bytes, stage: str
    ) -> bytes:
        """Universal data hook called at every compress pipeline stage.

        Args:
            ctx:   Mutable pipeline context.
            data:  Data payload for the current stage (may be empty).
            stage: Pipeline stage identifier:
                   - ``'raw'``            — original file bytes
                   - ``'post_freq'``      — frequency table (as bytes)
                   - ``'post_encode'``    — encoded bitstream
                   - ``'pre_write'``      — final bytes about to hit disk

        Returns:
            The (possibly modified) data bytes.
        """
        return data  # default: pass-through

    @abstractmethod
    def on_compress_done(
        self, ctx: "CompressContext", stats: "CompressStats"
    ) -> None:
        """Called after the compressed file is fully written.

        Use this for cleanup, uploading, sending notifications, etc.
        """
        ...

    # ── Decompress side ──────────────────────────────────────────────────

    @abstractmethod
    def on_decompress_start(self, ctx: "DecompressContext") -> None:
        """Called before any decompression work begins."""
        ...

    @abstractmethod
    def on_decompress_data(
        self, ctx: "DecompressContext", data: bytes, stage: str
    ) -> bytes:
        """Universal data hook called at every decompress pipeline stage.

        Args:
            ctx:   Mutable pipeline context.
            data:  Data payload for the current stage.
            stage: Pipeline stage identifier:
                   - ``'raw_header'``   — raw header bytes (can inspect before decode)
                   - ``'post_decode'``  — decoded original bytes
                   - ``'pre_write'``    — bytes about to be written to output

        Returns:
            The (possibly modified) data bytes.
        """
        return data  # default: pass-through

    @abstractmethod
    def on_decompress_done(
        self, ctx: "DecompressContext", stats: "DecompressStats"
    ) -> None:
        """Called after decompressed output is fully written."""
        ...

    # ── Error handling ───────────────────────────────────────────────────

    @abstractmethod
    def on_error(
        self,
        ctx: "CompressContext | DecompressContext",
        error: Exception,
    ) -> None:
        """Called if the pipeline fails at any stage.

        Use this for cleanup: delete partial output files, roll back
        remote state, log the error with full context, etc.
        """
        ...

    # ── Header persistence ───────────────────────────────────────────────

    @abstractmethod
    def get_extension_data(self) -> dict:
        """Return custom data to persist into the HCF header extension JSON.

        The engine merges every registered extension's dict under its
        ``extension_id`` key, so there is no risk of key collision.
        """
        ...

    @abstractmethod
    def set_extension_data(self, data: dict) -> None:
        """Restore custom data read from the HCF header extension JSON.

        Called during decompression after the header is parsed.
        """
        ...
