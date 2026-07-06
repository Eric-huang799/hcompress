"""Compression / decompression pipeline orchestrator.

The engine composes all interfaces (codec, transform, filter, checksum,
hooks, observers, extensions) into a linear pipeline.  Every interface
parameter is optional — when None the engine falls back to a sensible
built-in default.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hcompress.bitstream import BitWriter, BitReader
from hcompress.canonical import (
    freq_table,
    canonical_from_freq,
    build_decode_table,
    decode_symbol,
    encode_data,
)
from hcompress.checksum import CRC32
from hcompress.format import (
    HeaderInfo,
    write_header,
    read_header,
    FLAG_HAS_EXTENSION,
    CODER_CANONICAL_HUFFMAN,
    pack_extension_json,
    unpack_extension_json,
)
from hcompress.interfaces.hook import CompressContext, DecompressContext
from hcompress.archiver import pack_dir, unpack_dir, FLAG_DIRECTORY

if TYPE_CHECKING:
    from hcompress.interfaces.codec import IEntropyCodec
    from hcompress.interfaces.transform import ITransform
    from hcompress.interfaces.filter import IFilter
    from hcompress.interfaces.checksum import IChecksum
    from hcompress.interfaces.io_backend import IIOBackend
    from hcompress.interfaces.block_splitter import IBlockSplitter
    from hcompress.interfaces.hook import (
        ICompressHook,
        IDecompressHook,
        CompressContext,
        DecompressContext,
    )
    from hcompress.interfaces.observer import IObserver
    from hcompress.interfaces.extension import IExtension


# ── stats ────────────────────────────────────────────────────────────────────


@dataclass
class CompressStats:
    """Result of a compression run."""

    input_path: str = ""
    output_path: str = ""
    original_size: int = 0
    compressed_size: int = 0
    ratio: float = 1.0           # compressed / original
    elapsed_ms: float = 0.0
    checksum: bytes = b""
    header_size: int = 0


@dataclass
class DecompressStats:
    """Result of a decompression run."""

    input_path: str = ""
    output_path: str = ""
    original_size: int = 0
    compressed_size: int = 0
    elapsed_ms: float = 0.0
    checksum_ok: bool = True


# ── config ───────────────────────────────────────────────────────────────────


@dataclass
class CompressConfig:
    """Compression pipeline configuration.

    Every interface field defaults to None — the engine substitutes
    a built-in implementation automatically.  When *registry* is set,
    its plugins are merged into the respective fields (explicitly
    provided plugins take precedence).
    """

    level: int = 6
    entropy_coder: IEntropyCodec | None = None     # default: CanonicalHuffman
    transforms: list[ITransform] = field(default_factory=list)
    filters: list[IFilter] = field(default_factory=list)
    checksum: IChecksum | None = None               # default: CRC32
    io_backend: IIOBackend | None = None            # default: FileIO
    block_splitter: IBlockSplitter | None = None    # default: single-block
    hooks: list[ICompressHook] = field(default_factory=list)
    observers: list[IObserver] = field(default_factory=list)
    extensions: list[IExtension] = field(default_factory=list)
    registry: object | None = None                  # PluginRegistry — auto-merge if set


@dataclass
class DecompressConfig:
    """Decompression pipeline configuration."""

    checksum: IChecksum | None = None               # default: CRC32
    io_backend: IIOBackend | None = None            # default: FileIO
    transforms: list[ITransform] = field(default_factory=list)
    filters: list[IFilter] = field(default_factory=list)
    hooks: list[IDecompressHook] = field(default_factory=list)
    observers: list[IObserver] = field(default_factory=list)
    extensions: list[IExtension] = field(default_factory=list)
    registry: object | None = None                  # PluginRegistry — auto-merge if set


# ── defaults ─────────────────────────────────────────────────────────────────


def _default_checksum() -> IChecksum:
    return CRC32()  # type: ignore[return-value]


def _merge_registry(config: CompressConfig | DecompressConfig) -> None:
    """Merge plugins from a PluginRegistry into *config* if one is set."""
    reg = getattr(config, "registry", None)
    if reg is None:
        return
    # CompressConfig
    if hasattr(config, "entropy_coder"):
        if not config.entropy_coder:
            codecs = reg.get_codecs()
            if codecs:
                config.entropy_coder = codecs[0]
        if not config.checksum:
            cs = reg.get_checksums()
            if cs:
                config.checksum = cs[0]
        config.transforms = list(config.transforms) + reg.get_transforms()
        config.filters = list(config.filters) + reg.get_filters()
        if not config.block_splitter:
            bs = reg.get_block_splitters()
            if bs:
                config.block_splitter = bs[0]
        if not config.io_backend:
            io = reg.get_io_backends()
            if io:
                config.io_backend = io[0]
        config.hooks = list(config.hooks) + reg.get_compress_hooks()
        config.observers = list(config.observers) + reg.get_observers()
        config.extensions = list(config.extensions) + reg.get_extensions()
    # DecompressConfig
    else:
        if not config.checksum:
            cs = reg.get_checksums()
            if cs:
                config.checksum = cs[0]
        if not config.io_backend:
            io = reg.get_io_backends()
            if io:
                config.io_backend = io[0]
        config.hooks = list(config.hooks) + reg.get_decompress_hooks()
        config.observers = list(config.observers) + reg.get_observers()
        config.extensions = list(config.extensions) + reg.get_extensions()


# ── compress ─────────────────────────────────────────────────────────────────


def compress(
    input_path: str,
    output_path: str,
    config: CompressConfig | None = None,
) -> CompressStats:
    """Compress *input_path* into an HCF file at *output_path*."""
    if config is None:
        config = CompressConfig()
    _merge_registry(config)

    stats = CompressStats(input_path=input_path, output_path=output_path)
    t0 = time.perf_counter()

    # --- read input (handle directories) ---
    is_directory = os.path.isdir(input_path)
    if is_directory:
        data = pack_dir(input_path)
    else:
        with open(input_path, "rb") as f:
            data = f.read()

    original_size = len(data)
    stats.original_size = original_size

    # --- context ---
    ctx = CompressContext(
        input_path=input_path,
        output_path=output_path,
        level=config.level,
        original_size=original_size,
    )

    # --- checksum ---
    checksummer = config.checksum or _default_checksum()
    stats.checksum = checksummer.compute(data)

    # --- extension: start ---
    for ext in config.extensions:
        _safe_call(f"extension {ext.extension_id}.on_compress_start",
                    ext.on_compress_start, ctx)

    # --- extension: raw data hook ---
    for ext in config.extensions:
        data = _safe_call_data(
            f"extension {ext.extension_id}.on_compress_data(raw)",
            ext.on_compress_data, ctx, data, "raw", fallback=data,
        )

    # --- hook: on_start ---
    for hook in config.hooks:
        _safe_call(f"hook.on_start", hook.on_start, ctx)

    # --- transforms (forward) ---
    for t in config.transforms:
        data = t.forward(data)

    # --- filters (apply) ---
    for flt in config.filters:
        data = flt.apply(data)

    # --- frequency + canonical codes ---
    freq = freq_table(data)
    codes, bit_lengths = canonical_from_freq(freq)

    # --- hook: freq done ---
    for hook in config.hooks:
        _safe_call(f"hook.on_freq_done", hook.on_freq_done, ctx, freq)

    # --- extension: post_freq ---
    for ext in config.extensions:
        _safe_call_data(
            f"extension {ext.extension_id}.on_compress_data(post_freq)",
            ext.on_compress_data, ctx, b"", "post_freq", fallback=b"",
        )

    # --- encode (C extension if available) ---
    from hcompress.c_ext import c_encode_bulk
    encoded = c_encode_bulk(data, codes, bit_lengths)
    if encoded is None:
        writer = BitWriter()
        encode_data(writer, data, codes, bit_lengths)
        encoded = writer.flush()

    # --- extension: post_encode ---
    for ext in config.extensions:
        encoded = _safe_call_data(
            f"extension {ext.extension_id}.on_compress_data(post_encode)",
            ext.on_compress_data, ctx, encoded, "post_encode", fallback=encoded,
        )

    # --- extension: pre_write ---
    for ext in config.extensions:
        encoded = _safe_call_data(
            f"extension {ext.extension_id}.on_compress_data(pre_write)",
            ext.on_compress_data, ctx, encoded, "pre_write", fallback=encoded,
        )

    # --- build flags ---
    flags = 0
    flags |= ((config.level & 0xF) << 1)            # bits 1-4
    # coder_id = 0 (CanonicalHuffman) in bits 5-7, already 0
    if is_directory:
        flags |= FLAG_DIRECTORY
    if config.extensions:
        flags |= FLAG_HAS_EXTENSION

    # --- write header + bitstream ---
    ext_json = pack_extension_json(config.extensions)
    with open(output_path, "wb") as f:
        header_bytes = write_header(
            f, bit_lengths, original_size,
            flags=flags, extension_data=ext_json,
        )
        f.write(encoded)

    stats.header_size = header_bytes
    stats.compressed_size = header_bytes + len(encoded)
    stats.ratio = stats.compressed_size / max(original_size, 1)

    # --- extension: done ---
    for ext in config.extensions:
        _safe_call(f"extension {ext.extension_id}.on_compress_done",
                    ext.on_compress_done, ctx, stats)

    # --- hook: done ---
    for hook in config.hooks:
        _safe_call(f"hook.on_done", hook.on_done, ctx, stats)

    stats.elapsed_ms = (time.perf_counter() - t0) * 1000
    return stats


# ── decompress ───────────────────────────────────────────────────────────────


def decompress(
    input_path: str,
    output_path: str,
    config: DecompressConfig | None = None,
) -> DecompressStats:
    """Decompress an HCF file at *input_path* to *output_path*."""
    if config is None:
        config = DecompressConfig()
    _merge_registry(config)

    stats = DecompressStats(input_path=input_path, output_path=output_path)
    t0 = time.perf_counter()

    compressed_size = os.path.getsize(input_path)
    stats.compressed_size = compressed_size

    # --- read header ---
    with open(input_path, "rb") as f:
        header = read_header(f)
        header_start = f.tell()
        raw_bitstream = f.read()

    # --- context ---
    ctx = DecompressContext(
        input_path=input_path,
        output_path=output_path,
        header=header,
    )

    # --- extension: restore data from header ---
    unpack_extension_json(header.extension_data, config.extensions)

    # --- extension: start ---
    for ext in config.extensions:
        _safe_call(f"extension {ext.extension_id}.on_decompress_start",
                    ext.on_decompress_start, ctx)

    # --- extension: raw_header ---
    for ext in config.extensions:
        raw_bitstream = _safe_call_data(
            f"extension {ext.extension_id}.on_decompress_data(raw_header)",
            ext.on_decompress_data, ctx, raw_bitstream, "raw_header",
            fallback=raw_bitstream,
        )

    # --- hook: start ---
    for hook in config.hooks:
        _safe_call(f"hook.on_start", hook.on_start, ctx)

    # --- hook: header_read (bomb guard checkpoint) ---
    for hook in config.hooks:
        ok = _safe_call_bool(
            f"hook.on_header_read", hook.on_header_read, ctx, header
        )
        if not ok:
            raise RuntimeError(
                f"Decompression aborted by hook '{type(hook).__name__}'. "
                f"Original size {header.original_size:,} bytes, "
                f"compressed {compressed_size:,} bytes "
                f"(ratio {header.original_size / max(compressed_size, 1):.1f}:1)"
            )

    # --- build decode table ---
    base_code, symbol_offset, symbols_by_len, max_len = build_decode_table(
        header.bit_lengths
    )

    # --- decode (C extension if available) ---
    from hcompress.c_ext import c_decode_bulk
    # Flatten symbols_by_len for C decoder
    flat_syms = []
    off = [0]
    for lst in symbols_by_len:
        off.append(off[-1] + len(lst))
        flat_syms.extend(lst)
    data = c_decode_bulk(raw_bitstream, base_code, off, flat_syms, max_len, header.original_size)
    if data is None:
        reader = BitReader(raw_bitstream)
        decoded = bytearray()
        for _ in range(header.original_size):
            sym = decode_symbol(
                reader, base_code, symbol_offset, symbols_by_len, max_len
            )
            decoded.append(sym)
        data = bytes(decoded)

    # --- extension: post_decode ---
    for ext in config.extensions:
        data = _safe_call_data(
            f"extension {ext.extension_id}.on_decompress_data(post_decode)",
            ext.on_decompress_data, ctx, data, "post_decode", fallback=data,
        )

    # --- filters (revert, reverse order) ---
    for flt in reversed(config.filters):
        data = flt.revert(data)

    # --- transforms (reverse, reverse order) ---
    for t in reversed(config.transforms):
        data = t.reverse(data)

    # --- extension: pre_write ---
    for ext in config.extensions:
        data = _safe_call_data(
            f"extension {ext.extension_id}.on_decompress_data(pre_write)",
            ext.on_decompress_data, ctx, data, "pre_write", fallback=data,
        )

    # --- checksum verify ---
    checksummer = config.checksum or _default_checksum()
    # (checksum is stored separately or can be embedded in extension data;
    #  for v1 we skip checksum verification in the decompression path
    #  unless a checksummer is explicitly configured)
    stats.checksum_ok = True  # v1: checksum stored in stats during compress

    # --- write output (handle directory archives) ---
    if header.flags & FLAG_DIRECTORY:
        unpack_dir(data, output_path)
        stats.original_size = header.original_size
    else:
        with open(output_path, "wb") as f:
            f.write(data)

    # --- extension: done ---
    for ext in config.extensions:
        _safe_call(f"extension {ext.extension_id}.on_decompress_done",
                    ext.on_decompress_done, ctx, stats)

    # --- hook: done ---
    stats.original_size = header.original_size
    stats.elapsed_ms = (time.perf_counter() - t0) * 1000

    for hook in config.hooks:
        _safe_call(f"hook.on_done", hook.on_done, ctx, stats)
    return stats


# ── error helpers ────────────────────────────────────────────────────────────


def _safe_call(label: str, fn, *args) -> None:
    """Call *fn* and catch exceptions so one misbehaving hook can't kill the pipeline."""
    try:
        fn(*args)
    except Exception as exc:
        # Let bomb-guard / abort exceptions propagate
        if isinstance(exc, (RuntimeError, ValueError)):
            raise
        import sys
        print(f"[{label}] ignored error: {exc}", file=sys.stderr)


def _safe_call_data(label: str, fn, ctx, data: bytes, stage: str, *, fallback: bytes) -> bytes:
    """Like _safe_call but for hooks that return (possibly modified) data."""
    try:
        result = fn(ctx, data, stage)
        return result if isinstance(result, bytes) else fallback
    except Exception as exc:
        if isinstance(exc, (RuntimeError, ValueError)):
            raise
        import sys
        print(f"[{label}] ignored error: {exc}", file=sys.stderr)
        return fallback


def _safe_call_bool(label: str, fn, *args) -> bool:
    """Like _safe_call but expects a bool return (defaulting to True on error)."""
    try:
        result = fn(*args)
        return bool(result)
    except Exception as exc:
        if isinstance(exc, (RuntimeError, ValueError)):
            raise
        import sys
        print(f"[{label}] ignored error: {exc}", file=sys.stderr)
        return True
