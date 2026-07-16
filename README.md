# HCompress 统一仓库

**数据结构课程设计 — 基于规范哈夫曼编码的高性能压缩工具**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](https://github.com)
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

## 仓库结构

```
hcompress/
├── hcompress/          # Python 核心引擎（CLI + GUI + 插件系统）
│   ├── engine.py       # 压缩管线编排
│   ├── canonical.py    # 规范哈夫曼编解码
│   ├── interfaces/     # 10 个插件抽象接口
│   ├── plugins/        # 插件注册表 + 内置插件
│   └── c_ext/          # C 扩展加速
├── electron/           # Electron 桌面应用（V2.3.0 跨平台 GUI）
├── android/            # Android 移动端应用
├── docs/               # PPT、结题报告、Demo 文档
├── pyproject.toml
└── hcompress.spec      # PyInstaller 打包配置
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
