"""CLI — Click command group with Rich terminal UI."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from hcompress import __version__
from hcompress.engine import (
    CompressConfig,
    DecompressConfig,
    CompressStats,
    DecompressStats,
    compress,
    decompress,
)
from hcompress.format import read_header

# Force UTF-8 on Windows to avoid Rich GBK encoding errors
import sys as _sys
if _sys.platform == "win32":
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

console = Console()


# ── helpers ──────────────────────────────────────────────────────────────────


def _format_size(n: int) -> str:
    """Human-readable byte size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _format_ratio(ratio: float) -> str:
    """Compression ratio as a readable percentage."""
    pct = ratio * 100
    saved = 100 - pct
    if saved > 0:
        return f"{pct:.1f}%  ([green]-{saved:.1f}%[/])"
    else:
        return f"{pct:.1f}%  ([red]+{abs(saved):.1f}%[/])"


def _print_stats_compress(stats: CompressStats) -> None:
    """Render compression result as a Rich table."""
    table = Table(title="🔥  Compress  Complete", expand=False)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Input", stats.input_path)
    table.add_row("Output", stats.output_path)
    table.add_row("Original", _format_size(stats.original_size))
    table.add_row("Compressed", _format_size(stats.compressed_size))
    table.add_row("Ratio", _format_ratio(stats.ratio))
    table.add_row("Header", _format_size(stats.header_size))
    table.add_row("Time", f"{stats.elapsed_ms:.1f} ms")
    speed = stats.original_size / max(stats.elapsed_ms / 1000, 0.001)
    table.add_row("Speed", f"{_format_size(int(speed))}/s")

    console.print(table)


def _print_stats_decompress(stats: DecompressStats) -> None:
    """Render decompression result as a Rich table."""
    table = Table(title="🧊  Decompress  Complete", expand=False)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Input", stats.input_path)
    table.add_row("Output", stats.output_path)
    table.add_row("Decompressed", _format_size(stats.original_size))
    table.add_row("Time", f"{stats.elapsed_ms:.1f} ms")
    speed = stats.original_size / max(stats.elapsed_ms / 1000, 0.001)
    table.add_row("Speed", f"{_format_size(int(speed))}/s")
    table.add_row("Checksum", "[green]✓ OK[/]" if stats.checksum_ok else "[red]✗ FAIL[/]")

    console.print(table)


def _output_path(input_path: str, ext: str) -> str:
    """Generate default output path — append extension, don't replace."""
    return input_path + ext


# ── CLI group ────────────────────────────────────────────────────────────────


@click.group()
@click.version_option(version=__version__, prog_name="hcompress")
@click.pass_context
def main(ctx: click.Context) -> None:
    """hcompress — Canonical Huffman compression tool."""
    ctx.ensure_object(dict)


# ── compress ─────────────────────────────────────────────────────────────────


@main.command(name="c")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output .hcf path (default: <input>.hcf)")
@click.option("--level", type=click.IntRange(0, 9), default=6, help="Compression level (0-9)")
@click.option("-f", "--force", is_flag=True, help="Overwrite existing output file")
@click.option("--no-checksum", is_flag=True, help="Skip CRC-32 (not recommended)")
@click.option("--plugin-dir", multiple=True, help="Extra plugin search directory")
def compress_cmd(
    input_path: str, output: str | None, level: int, force: bool, no_checksum: bool,
    plugin_dir: tuple[str, ...],
) -> None:
    """Compress INPUT_PATH into an HCF archive."""
    out = output or _output_path(input_path, ".hcf")

    if os.path.exists(out) and not force:
        console.print(f"[red]✗[/] Output file [bold]{out}[/] already exists. Use [bold]-f[/] to overwrite.")
        raise SystemExit(1)

    from hcompress.plugins import PluginRegistry
    registry = PluginRegistry()
    registry.discover(list(plugin_dir))
    registry.discover_builtin()
    registry.discover_external()

    config = CompressConfig(level=level, registry=registry)

    _run_with_progress(
        lambda: compress(input_path, out, config),
        label="Compressing",
        input_path=input_path,
    )


# ── decompress ───────────────────────────────────────────────────────────────


@main.command(name="d")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output file path (default: strip .hcf)")
@click.option("-f", "--force", is_flag=True, help="Overwrite existing output file")
@click.option("--no-checksum", is_flag=True, help="Skip CRC-32 verification")
@click.option("--no-bomb-guard", is_flag=True, help="Disable compression-bomb detection")
@click.option("--plugin-dir", multiple=True, help="Extra plugin search directory")
def decompress_cmd(
    input_path: str, output: str | None, force: bool, no_checksum: bool,
    no_bomb_guard: bool, plugin_dir: tuple[str, ...],
) -> None:
    """Decompress an HCF archive (or other supported format)."""
    # Guess output name
    if output:
        out = output
    else:
        p = Path(input_path)
        if p.suffix.lower() == ".hcf":
            out = str(p.with_suffix(""))
        else:
            out = str(p) + ".out"

    # If not HCF, try format handler plugins
    if not input_path.lower().endswith(".hcf"):
        try:
            from hcompress.plugins.builtin.formats import detect, decompress as fmt_decompress
            fmt = detect(input_path)
        except ImportError:
            fmt = None
        if fmt:
            console.print(f"[cyan]检测到格式: {fmt}[/]")
            if os.path.exists(out) and not force:
                console.print(f"[red]✗[/] Output already exists. Use [bold]-f[/] to overwrite.")
                raise SystemExit(1)
            out_dir = output or os.path.dirname(input_path)
            fmt_decompress(input_path, out_dir)
            console.print(f"[green]✓[/] 解压完成 → [bold]{out_dir}[/]")
            return
        else:
            console.print(f"[yellow]⚠[/] 未知格式，尝试按 HCF 处理...")

    if os.path.exists(out) and not force:
        console.print(f"[red]✗[/] Output file [bold]{out}[/] already exists. Use [bold]-f[/] to overwrite.")
        raise SystemExit(1)

    from hcompress.plugins import PluginRegistry
    registry = PluginRegistry()
    registry.discover(list(plugin_dir))
    if not no_bomb_guard:
        registry.discover_builtin()
    registry.discover_external()

    config = DecompressConfig(registry=registry)

    _run_with_progress(
        lambda: decompress(input_path, out, config),
        label="Decompressing",
        input_path=input_path,
    )


# ── info ─────────────────────────────────────────────────────────────────────


@main.command(name="list")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--json", "as_json", is_flag=True, hidden=True)
def list_cmd(input_path: str, as_json: bool = False) -> None:
    """List files inside a directory HCF archive."""
    try:
        from hcompress.format import read_header
        from hcompress.canonical import build_decode_table, decode_symbol
        from hcompress.bitstream import BitReader
        from hcompress.c_ext import c_decode_bulk
        from hcompress.archiver import list_archive, is_dir_archive

        with open(input_path, "rb") as f:
            header = read_header(f)
            raw_bitstream = f.read()
        if not is_dir_archive(header.flags):
            console.print("[yellow]⚠[/] 不是目录归档文件")
            raise SystemExit(1)

        # Decode in-memory
        base_code, symbol_offset, symbols_by_len, max_len = build_decode_table(header.bit_lengths)
        flat_syms = []; off = [0]
        for lst in symbols_by_len: off.append(off[-1] + len(lst)); flat_syms.extend(lst)
        data = c_decode_bulk(raw_bitstream, base_code, off, flat_syms, max_len, header.original_size)
        if data is None:
            reader = BitReader(raw_bitstream)
            decoded = bytearray()
            for _ in range(header.original_size):
                decoded.append(decode_symbol(reader, base_code, symbol_offset, symbols_by_len, max_len))
            data = bytes(decoded)

        entries = list_archive(data)

        if as_json:
            import json as _json
            print(_json.dumps({"entries": entries, "count": len(entries), "original_size": header.original_size}, ensure_ascii=False))
            return

        from rich.table import Table
        table = Table(title=f"📁 归档内容 — {os.path.basename(input_path)}", expand=False)
        table.add_column("文件", style="cyan")
        table.add_column("大小", style="white", justify="right")
        total = 0
        for e in entries:
            table.add_row(e["name"], _format_size(e["size"]))
            total += e["size"]
        table.add_row("[bold]合计[/]", f"[bold]{_format_size(total)}[/]")
        console.print(table)
    except Exception as exc:
        console.print(f"[red]✗[/] {exc}")
        raise SystemExit(1)


@main.command(name="info")
@click.argument("input_path", type=click.Path(exists=True))
def info_cmd(input_path: str) -> None:
    """Display HCF file header information."""
    try:
        with open(input_path, "rb") as f:
            header = read_header(f)
            remaining = os.path.getsize(input_path) - f.tell()
    except Exception as exc:
        console.print(f"[red]✗[/] Failed to read HCF header: {exc}")
        raise SystemExit(1)

    # Count used symbols
    used = sum(1 for bl in header.bit_lengths if bl > 0)
    max_bl = max(header.bit_lengths) if used > 0 else 0

    table = Table(title=f"📦  HCF Info  —  {os.path.basename(input_path)}", expand=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Version", str(header.version))
    table.add_row("Flags", f"0x{header.flags:04X}")
    table.add_row("Compression level", str(header.compression_level))
    table.add_row("Entropy coder", f"Canonical Huffman (id={header.coder_id})")
    table.add_row("Has extension data", "Yes" if header.has_extension else "No")
    table.add_row("Symbols used", f"{used} / 256")
    table.add_row("Max code length", f"{max_bl} bits")
    table.add_row("Original size", f"{_format_size(header.original_size)} ({header.original_size:,} bytes)")
    table.add_row("Compressed payload", _format_size(remaining))
    if header.original_size > 0:
        table.add_row("Est. ratio", _format_ratio(remaining / header.original_size))
    if header.extension_data:
        try:
            import json
            ext_str = json.dumps(json.loads(header.extension_data), indent=2, ensure_ascii=False)
        except Exception:
            ext_str = header.extension_data.decode("utf-8", errors="replace")
        table.add_row("Extension data", ext_str[:500])

    console.print(table)


# ── bench ────────────────────────────────────────────────────────────────────


@main.group(name="plugin")
def plugin_group() -> None:
    """Plugin development commands."""


@plugin_group.command(name="new")
@click.argument("name")
@click.option("--type", "plugin_type", default="decompress-hook",
              type=click.Choice([
                  "decompress-hook", "compress-hook", "extension",
                  "checksum", "transform", "codec", "filter",
                  "matchfinder", "io-backend", "block-splitter", "observer",
              ]),
              help="Plugin type")
@click.option("-o", "--output-dir", default=".", help="Output directory")
def plugin_new(name: str, plugin_type: str, output_dir: str) -> None:
    """Scaffold a new plugin from a template.

    \b
    Examples:
      hcompress plugin new my-bomb-guard --type decompress-hook
      hcompress plugin new aes-encrypt --type extension -o ./plugins/
    """
    from hcompress.plugins.sdk import scaffold
    path = scaffold(name, plugin_type, output_dir)
    console.print(f"[green]✓[/] Plugin scaffolded → [bold]{path}[/]")
    console.print(f"    Edit the file and place it in a plugin directory.")
    console.print(f"    Then use [bold]--plugin-dir[/] to load it at runtime.")


@plugin_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, hidden=True, help="Output as JSON (for IPC)")
def plugin_list(as_json: bool = False) -> None:
    """List available plugin types and built-in plugins."""
    from hcompress.plugins import PluginRegistry
    reg = PluginRegistry()
    reg.discover_builtin()
    reg.discover_external()
    info = reg.get_all()

    if as_json:
        import json as _json
        print(_json.dumps(info, ensure_ascii=False), flush=True)
        return

    from rich.table import Table
    table.add_column("Type", style="cyan")
    table.add_column("Base Class", style="white")
    table.add_column("Use Case", style="dim")

    table.add_row("decompress-hook", "BaseDecompressHook", "Bomb guard, nesting detector, logging")
    table.add_row("compress-hook",   "BaseCompressHook",   "Metrics, logging, pre-flight checks")
    table.add_row("extension",       "BaseExtension",      "Encryption, signing, metadata, AI, ...")
    table.add_row("checksum",        "BaseChecksum",       "Custom hash / integrity check")
    table.add_row("transform",       "BaseTransform",      "BWT, MTF, RLE, delta encoding")
    table.add_row("codec",           "BaseCodec",          "Custom entropy coder (ANS, Arithmetic, ...)")
    table.add_row("filter",          "BaseFilter",         "Pre-processing (delta, PNG predictor, ...)")
    table.add_row("matchfinder",     "BaseMatchFinder",    "LZ dictionary matching")
    table.add_row("io-backend",      "BaseIOBackend",      "Custom I/O (S3, mmap, socket, ...)")
    table.add_row("block-splitter",  "BaseBlockSplitter",  "Block partitioning strategy")
    table.add_row("observer",        "BaseObserver",       "Progress / event / audit logging")
    console.print(table)

    # Show built-in
    from hcompress.plugins import PluginRegistry
    reg = PluginRegistry()
    reg.discover_builtin()
    reg.discover_external()
    info = reg.get_all()
    plugins = info["plugins"]
    if plugins:
        console.print(f"\n[dim]Built-in plugins loaded: {info['count']} (enabled: {info['count_enabled']})[/]")
        for p in plugins:
            status = "[green]●[/]" if p["enabled"] else "[red]○[/]"
            console.print(
                f"  {status} {p['name']}  [dim]v{p['version']}[/]  "
                f"([dim]{p['plugin_type']}[/])  "
                f"→ {p['description']}"
            )


@main.command(name="tui")
def tui_cmd() -> None:
    """Launch the Textual terminal user interface."""
    from hcompress.tui import main as tui_main
    tui_main()


@main.command(name="gui")
def gui_cmd() -> None:
    """Launch the graphical user interface."""
    from hcompress.gui import main as gui_main
    gui_main()


@main.command(name="bench")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("-n", "--iterations", type=int, default=5, help="Number of rounds")
def bench_cmd(input_path: str, iterations: int) -> None:
    """Benchmark compression + decompression round-trip."""
    console.print(Panel.fit(
        f"[bold]Benchmark[/]  {os.path.basename(input_path)}  ×  {iterations} rounds",
        border_style="blue",
    ))

    tmp = input_path + ".bench.hcf"
    c_times: list[float] = []
    d_times: list[float] = []
    original = os.path.getsize(input_path)

    for i in range(iterations):
        # Compress
        t0 = time.perf_counter()
        stats = compress(input_path, tmp)
        c_ms = (time.perf_counter() - t0) * 1000
        c_times.append(c_ms)

        # Decompress
        restored = input_path + ".bench.out"
        t0 = time.perf_counter()
        decompress(tmp, restored)
        d_ms = (time.perf_counter() - t0) * 1000
        d_times.append(d_ms)

        # Cleanup
        try:
            os.remove(tmp)
            os.remove(restored)
        except OSError:
            pass

    # Summary
    def _avg(vals): return sum(vals) / len(vals)

    table = Table(title="📊  Benchmark Results", expand=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Avg", style="green")
    table.add_column("Min", style="white")
    table.add_column("Max", style="white")

    table.add_row(
        "Compress time",
        f"{_avg(c_times):.1f} ms",
        f"{min(c_times):.1f} ms",
        f"{max(c_times):.1f} ms",
    )
    table.add_row(
        "Decompress time",
        f"{_avg(d_times):.1f} ms",
        f"{min(d_times):.1f} ms",
        f"{max(d_times):.1f} ms",
    )
    c_speed = original / max(_avg(c_times) / 1000, 0.001)
    d_speed = original / max(_avg(d_times) / 1000, 0.001)
    table.add_row("Compress speed", f"{_format_size(int(c_speed))}/s", "", "")
    table.add_row("Decompress speed", f"{_format_size(int(d_speed))}/s", "", "")
    table.add_row("Compressed size", _format_size(stats.compressed_size), "", "")
    table.add_row("Ratio", _format_ratio(stats.ratio), "", "")

    console.print(table)


# ── progress wrapper ─────────────────────────────────────────────────────────


def _run_with_progress(fn, *, label: str, input_path: str) -> None:
    """Run *fn* with a Rich indeterminate progress spinner."""
    fname = os.path.basename(input_path)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"[cyan]{label}[/] [bold]{fname}[/]", total=None)
        try:
            result = fn()
            progress.update(task, completed=1, total=1,
                            description=f"[green]✓ Done[/] [bold]{fname}[/]")
        except Exception as exc:
            progress.stop()
            console.print(Panel(
                f"[red bold]Error[/]\n{exc}",
                border_style="red",
            ))
            raise SystemExit(1)

    # Print result table
    if isinstance(result, CompressStats):
        _print_stats_compress(result)
    elif isinstance(result, DecompressStats):
        _print_stats_decompress(result)
