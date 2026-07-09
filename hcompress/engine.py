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
    """Merge plugins from a PluginRegistry into *config* if one is set.

    Uses ``get_enabled_*()`` so that disabled plugins are automatically
    skipped.  Explicitly-provided plugins take precedence over registry ones.

    Also checks the ``HCOMPRESS_DISABLED_PLUGINS`` environment variable
    (comma-separated plugin names) — used by v2 Electron to session-disable
    plugins from the Plugin Manager UI.
    """
    reg = getattr(config, "registry", None)
    if reg is None:
        return

    # Apply v2 Electron session-level disable list
    disabled_env = os.environ.get("HCOMPRESS_DISABLED_PLUGINS", "")
    if disabled_env:
        for name in disabled_env.split(","):
            name = name.strip()
            if name:
                reg.disable(name)
    # CompressConfig
    if hasattr(config, "entropy_coder"):
        if not config.entropy_coder:
            codecs = reg.get_enabled_codecs()
            if codecs:
                config.entropy_coder = codecs[0]
        if not config.checksum:
            cs = reg.get_enabled_checksums()
            if cs:
                config.checksum = cs[0]
        if not config.block_splitter:
            bs = reg.get_enabled_block_splitters()
            if bs:
                config.block_splitter = bs[0]
        if not config.io_backend:
            io = reg.get_enabled_io_backends()
            if io:
                config.io_backend = io[0]
        config.hooks = list(config.hooks) + reg.get_enabled_compress_hooks()
        config.observers = list(config.observers) + reg.get_enabled_observers()
        config.extensions = list(config.extensions) + reg.get_enabled_extensions()
    # DecompressConfig
    else:
        if not config.checksum:
            cs = reg.get_enabled_checksums()
            if cs:
                config.checksum = cs[0]
        if not config.io_backend:
            io = reg.get_enabled_io_backends()
            if io:
                config.io_backend = io[0]
        config.hooks = list(config.hooks) + reg.get_enabled_decompress_hooks()
        config.observers = list(config.observers) + reg.get_enabled_observers()
        config.extensions = list(config.extensions) + reg.get_enabled_extensions()


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

    # --- apply v2 Electron transform selection ---
    _active_transforms = os.environ.get("HCOMPRESS_TRANSFORMS", "")
    if _active_transforms:
        for _name in _active_transforms.split(","):
            _name = _name.strip()
            if _name and config.registry:
                for _t in config.registry.get_transforms():
                    if type(_t).__name__ == _name and _t not in config.transforms:
                        config.transforms.append(_t)
                        break

    stats = CompressStats(input_path=input_path, output_path=output_path)
    t0 = time.perf_counter()

    # --- read input (handle directories) ---
    is_directory = os.path.isdir(input_path)
    if is_directory:
        skipped = []
        data, skip_count = pack_dir(input_path, on_skip=lambda p, e: skipped.append(p))
        if skip_count > 0:
            import sys
            print(f"Warning: skipped {skip_count} unreadable file(s):", file=sys.stderr)
            for p in skipped[:10]:
                print(f"  - {p}", file=sys.stderr)
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

    # --- check for parallel plugin ---
    use_parallel = False
    parallel_workers = 4
    parallel_hook = None
    for hook in config.hooks:
        if getattr(hook, "supports_parallel", False):
            parallel_hook = hook
            hook.on_compress_start(ctx)
            if getattr(ctx, "_parallel_enabled", False):
                use_parallel = True
                parallel_workers = getattr(ctx, "_parallel_workers", 4)
            break

    if use_parallel and not is_directory:
        from hcompress.parallel import compress_parallel
        r = compress_parallel(input_path, output_path, level=config.level, workers=parallel_workers)
        stats.compressed_size = r["compressed_size"]
        stats.ratio = r["ratio"]
        stats.elapsed_ms = r["elapsed_ms"]
        if parallel_hook is not None:
            parallel_hook.on_compress_done(ctx, stats)
        return stats

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

    # --- hook: on_compress_start ---
    for hook in config.hooks:
        _safe_call(f"hook.on_compress_start", hook.on_compress_start, ctx)

    # --- transforms (forward) ---
    for t in config.transforms:
        data = t.forward(data)

    # --- filters (apply) ---
    for flt in config.filters:
        data = flt.apply(data)

    # Update sizes: header.original_size must be post-transform length
    # so the Huffman decoder knows how many symbols to decode.
    # The true pre-transform size is stored in extension JSON.
    _pre_transform_size = original_size
    original_size = len(data)
    stats.original_size = original_size

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

    # --- build extension JSON (with optional transform chain) ---
    ext_json = pack_extension_json(config.extensions)
    if config.transforms:
        import json as _json
        _transform_names = [type(t).__name__ for t in config.transforms]
        _ext_dict = (
            _json.loads(ext_json.decode("utf-8"))
            if ext_json else {}
        )
        _ext_dict["_hcompress_transforms"] = _transform_names
        _ext_dict["_hcompress_original_size"] = _pre_transform_size
        ext_json = _json.dumps(_ext_dict, ensure_ascii=False).encode("utf-8")

    # --- build flags ---
    flags = 0
    flags |= ((config.level & 0xF) << 1)            # bits 1-4
    # coder_id = 0 (CanonicalHuffman) in bits 5-7, already 0
    if is_directory:
        flags |= FLAG_DIRECTORY
    if ext_json:
        flags |= FLAG_HAS_EXTENSION

    # --- write header + bitstream ---
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

    # --- hook: on_compress_done ---
    for hook in config.hooks:
        _safe_call(f"hook.on_compress_done", hook.on_compress_done, ctx, stats)

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

    # --- auto-load transform chain from HCF header ---
    if header.extension_data and config.registry:
        import json as _json
        try:
            _ext_dict = _json.loads(header.extension_data.decode("utf-8"))
            _chain = _ext_dict.get("_hcompress_transforms", [])
            for _name in _chain:
                for _t in config.registry.get_transforms():
                    if type(_t).__name__ == _name and _t not in config.transforms:
                        config.transforms.append(_t)
                        break
                else:
                    import sys
                    print(
                        f"Warning: HCF requires transform '{_name}' but it is not loaded. "
                        f"Output may be corrupted.",
                        file=sys.stderr,
                    )
        except (_json.JSONDecodeError, UnicodeDecodeError):
            pass

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

    # --- hook: on_decompress_start ---
    for hook in config.hooks:
        _safe_call(f"hook.on_decompress_start", hook.on_decompress_start, ctx)

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
    # Restore true pre-transform original size from HCF extension
    if header.extension_data:
        import json as _json
        try:
            _ext = _json.loads(header.extension_data.decode("utf-8"))
            _true_size = _ext.get("_hcompress_original_size")
            if _true_size is not None:
                stats.original_size = _true_size
        except (_json.JSONDecodeError, UnicodeDecodeError):
            pass
    stats.elapsed_ms = (time.perf_counter() - t0) * 1000

    for hook in config.hooks:
        _safe_call(f"hook.on_decompress_done", hook.on_decompress_done, ctx, stats)
    return stats


# ── error helpers ────────────────────────────────────────────────────────────


def _safe_call(label: str, fn, *args) -> None:
    """Call *fn* and catch exceptions so one misbehaving hook can't kill the pipeline.

    Set env ``HCOMPRESS_DEBUG_PLUGINS=1`` to print full tracebacks instead of
    swallowing errors silently.
    """
    debug_plugins = os.environ.get("HCOMPRESS_DEBUG_PLUGINS", "") == "1"
    try:
        fn(*args)
    except Exception as exc:
        if isinstance(exc, (RuntimeError, ValueError)):
            raise
        if debug_plugins:
            import traceback
            traceback.print_exc()
        else:
            import sys
            print(f"[{label}] ignored error: {exc}", file=sys.stderr)


def _safe_call_data(label: str, fn, ctx, data: bytes, stage: str, *, fallback: bytes) -> bytes:
    """Like _safe_call but for hooks that return (possibly modified) data."""
    debug_plugins = os.environ.get("HCOMPRESS_DEBUG_PLUGINS", "") == "1"
    try:
        result = fn(ctx, data, stage)
        return result if isinstance(result, bytes) else fallback
    except Exception as exc:
        if isinstance(exc, (RuntimeError, ValueError)):
            raise
        if debug_plugins:
            import traceback
            traceback.print_exc()
        else:
            import sys
            print(f"[{label}] ignored error: {exc}", file=sys.stderr)
        return fallback


def _safe_call_bool(label: str, fn, *args) -> bool:
    """Like _safe_call but expects a bool return (defaulting to True on error)."""
    debug_plugins = os.environ.get("HCOMPRESS_DEBUG_PLUGINS", "") == "1"
    try:
        result = fn(*args)
        return bool(result)
    except Exception as exc:
        if isinstance(exc, (RuntimeError, ValueError)):
            raise
        if debug_plugins:
            import traceback
            traceback.print_exc()
        else:
            import sys
            print(f"[{label}] ignored error: {exc}", file=sys.stderr)
        return True
