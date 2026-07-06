# hcompress

**High-performance Canonical Huffman compression tool with plugin architecture.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](https://github.com)
[![Tests](https://img.shields.io/badge/Tests-69%2F69%20passed-green)](tests/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Features

- **Canonical Huffman** — standard algorithm used by gzip, PNG, JPEG
- **C-accelerated** — encode/decode hot paths compiled to native code (**12× encode, 44× decode** speedup)
- **Plugin system** — 10 extension interfaces, scaffold CLI, one-command plugin generation
- **Bomb Guard** — compression-bomb detection with configurable expansion ratio threshold
- **HCF file format** — compact, extensible header with CRC integrity check
- **GUI + CLI** — tkinter graphical interface plus full-featured command-line tool
- **3D architecture demo** — interactive Three.js + ECharts visualization page

## Quick Start

### Download (Windows)

Grab the standalone `hcompress.exe` from [Releases](https://github.com/eric/hcompress/releases) — no Python required, double-click to launch the GUI.

### Install from source

```bash
git clone https://github.com/eric/hcompress.git
cd hcompress
pip install -e .
```

### Usage

```bash
# Command Line
hcompress c myfile.txt                    # compress → myfile.txt.hcf
hcompress d myfile.txt.hcf                # decompress → myfile.txt
hcompress info myfile.txt.hcf             # view file info
hcompress bench myfile.txt -n 10          # benchmark

# GUI
hcompress gui                             # launch graphical interface
hcompress plugin new my-guard --type decompress-hook   # scaffold a plugin
```

Or just drag any file onto `hcompress.exe` / `hcompress.bat`.

## Performance

| File Type | Size | Compressed | Ratio | Speed (C ext) |
|---|---|---|---|---|
| Plain text | 530 KB | 267 KB | **50.8%** | 5.9 MB/s |
| Python source | 128 KB | 68 KB | **53.1%** | 5.7 MB/s |
| Binary (uniform) | 100 KB | 100 KB | 100.3% | 5.8 MB/s |

C extension benchmarks vs pure Python on 530KB text:

| Operation | Pure Python | C Extension | Speedup |
|---|---|---|---|
| Encode | 385 ms | 88 ms | **4.4×** |
| Decode | 809 ms | 28 ms | **29.5×** |

## Architecture

```
┌──────────┐    ┌───────────┐    ┌─────────────────┐    ┌──────────┐    ┌─────────────┐
│  Input   │ →  │ Transforms │ →  │ Canonical Huffman │ →  │ CRC-32   │ →  │  HCF Output │
│  File    │    │  (opt.)    │    │  Encode / Decode   │    │ Checksum │    │  (.hcf)     │
└──────────┘    └───────────┘    └─────────────────┘    └──────────┘    └─────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
              IEntropyCodec    ICompressHook      IExtension  ← 10 pluggable interfaces
              ITransform       IDecompressHook
              IFilter          IObserver
              IMatchFinder     IIOBackend
              IChecksum        IBlockSplitter
```

### Plugin System — write a plugin in 4 lines

```python
from hcompress.plugins.sdk import BaseDecompressHook

class MyBombGuard(BaseDecompressHook):
    def on_header_read(self, ctx, header):
        if header.original_size / ctx.compressed_size > 100:
            raise RuntimeError("Suspicious expansion ratio!")
        return True
```

```bash
# Scaffold a plugin from template
hcompress plugin new my-guard --type decompress-hook

# Load and use
hcompress d file.hcf --plugin-dir ./my-plugins/
```

Built-in: **BombGuard** — detects compression bombs before decompression starts (default: 100:1 threshold, configurable).

## HCF File Format

```
Offset  Size   Field
------  ----   -----
0       4      Magic: 'HCF\x1a'
4       2      Version (uint16 LE)
6       2      Flags (coder ID, level, has_extension)
8       2      CRC-16 (header integrity)
10      2      Symbol count N (typically 256)
12      N      Bit-length table (1 byte per symbol)
12+N    8      Original size (uint64 LE)        ← bomb detection anchor
20+N    4      Extension data length (optional)
24+N    E      Extension data (JSON, pluggable)
```

## Project Structure

```
hcompress/
├── hcompress/
│   ├── interfaces/      # 10 ABC interfaces
│   ├── plugins/
│   │   ├── registry.py  # auto-discovery & loading
│   │   ├── builtin/     # BombGuard (built-in)
│   │   └── sdk/         # no-op base classes + scaffold
│   ├── c_ext/           # C-accelerated hot paths
│   ├── engine.py        # compression pipeline
│   ├── canonical.py     # Huffman tree & codec
│   ├── cli.py           # Click + Rich CLI
│   ├── gui.py           # tkinter GUI
│   └── format.py        # HCF header read/write
├── demo/index.html      # 3D architecture + ECharts demo
├── tests/               # 69 tests
└── dist/                # standalone .exe builds
```

## Build Standalone EXE

```bash
pip install pyinstaller
python -m PyInstaller --onefile --windowed \
  --name hcompress \
  --add-data "hcompress/c_ext/_hcompress.dll:." \
  --add-data "hcompress/plugins/builtin:plugins/builtin" \
  --collect-all rich --collect-all click \
  hcompress/launcher.py
```

Output: `dist/hcompress.exe` (~36 MB, zero dependencies).

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v          # 69 tests
python -m hcompress gui   # launch GUI
```

## License

MIT © Eric
