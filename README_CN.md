# hcompress

**基于 Canonical Huffman 的高性能压缩软件 — C 加速 · 插件架构 · 炸弹防护**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![Platform](https://img.shields.io/badge/平台-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]()
[![Tests](https://img.shields.io/badge/测试-69/69%20通过-green)](tests/)
[![License](https://img.shields.io/badge/协议-MIT-yellow)](LICENSE)

[English](README.md) | **中文**

---

## 功能特性

- **Canonical Huffman 算法** — gzip、PNG、JPEG 同款熵编码，压缩率稳定 50%
- **C 扩展加速** — 编解码热路径用 C 重写，编译为原生机器码（编码 **4.4×**，解码 **29.5×**）
- **插件系统** — 10 个可扩展接口，一键脚手架生成模板，扔目录里自动加载
- **炸弹检测** — 内置 BombGuard，解压前检测压缩包炸弹（默认 100:1 膨胀比阈值）
- **HCF 文件格式** — 紧凑可扩展的 header，含 CRC-16 完整性校验
- **GUI + CLI** — tkinter 图形界面 + Click/Rich 命令行，两种方式都能用
- **3D 架构演示** — Three.js + ECharts 交互式可视化页面

## 快速开始

### 下载（Windows）

去 [Releases](https://github.com/Eric-huang799/hcompress/releases) 下载 `hcompress.exe`（36 MB），**不需要安装 Python**，双击直接打开 GUI。

### 从源码安装

```bash
git clone https://github.com/Eric-huang799/hcompress.git
cd hcompress
pip install -e .
```

### 使用方式

```bash
# 命令行
hcompress c myfile.txt                    # 压缩 → myfile.txt.hcf
hcompress d myfile.txt.hcf                # 解压 → myfile.txt
hcompress info myfile.txt.hcf             # 查看文件信息
hcompress bench myfile.txt -n 10          # 性能测试

# 图形界面
hcompress gui                             # 启动 GUI

# 插件开发
hcompress plugin new 我的插件 --type decompress-hook   # 一键生成插件模板
hcompress plugin list                     # 查看可用插件类型
```

也可以直接把文件拖到 `hcompress.exe` 或 `hcompress.bat` 上，自动处理喵。

## 性能实测

| 文件类型 | 原始大小 | 压缩后 | 压缩率 | 速度（C 扩展） |
|---|---|---|---|---|
| 纯文本 | 530 KB | 267 KB | **50.8%** | 5.9 MB/s |
| Python 源码 | 128 KB | 68 KB | **53.1%** | 5.7 MB/s |
| 均匀二进制 | 100 KB | 100 KB | 100.3% | 5.8 MB/s |

C 扩展 vs 纯 Python 对比（530KB 文本）：

| 操作 | 纯 Python | C 扩展 | 加速比 |
|---|---|---|---|
| 编码 | 385 ms | 88 ms | **4.4×** |
| 解码 | 809 ms | 28 ms | **29.5×** |

## 架构总览

```
┌──────────┐    ┌───────────┐    ┌─────────────────┐    ┌──────────┐    ┌─────────────┐
│  输入文件 │ →  │  变换层    │ →  │ Canonical Huffman │ →  │ CRC-32   │ →  │  HCF 输出   │
│          │    │  (可选)    │    │  编码 / 解码       │    │ 校验     │    │  (.hcf)     │
└──────────┘    └───────────┘    └─────────────────┘    └──────────┘    └─────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
              IEntropyCodec    ICompressHook      IExtension  ← 10 个可插拔接口
              ITransform       IDecompressHook
              IFilter          IObserver
              IMatchFinder     IIOBackend
              IChecksum        IBlockSplitter
```

### 插件系统 — 4 行代码写一个插件

```python
from hcompress.plugins.sdk import BaseDecompressHook

class 我的炸弹检测(BaseDecompressHook):
    def on_header_read(self, ctx, header):
        if header.original_size / ctx.compressed_size > 100:
            raise RuntimeError("疑似压缩炸弹！膨胀比异常")
        return True
```

```bash
# 脚手架一键生成模板
hcompress plugin new 我的炸弹检测 --type decompress-hook

# 加载使用
hcompress d 文件.hcf --plugin-dir ./我的插件目录/
```

内置插件：**BombGuard**（炸弹检测）— 解压前读取 header 计算膨胀比，超阈值直接拒绝（默认 100:1，可配置）。

## 炸弹检测原理

```
HCF 文件 header 中存储了 original_size（原始文件大小）。
读完 276 字节的 header 后：

    膨胀比 = original_size / 压缩文件实际大小

    如果 膨胀比 > 阈值 (默认 100:1) → 💣 拒绝解压
    否则 → ✅ 正常解压

零 I/O 开销，不等解压数据就读完 header 就能判断。
```

即使攻击者篡改 header 中的 `original_size` 为 100GB，压缩文件本身只有 1KB，膨胀比高达 1 亿倍，瞬间被拦。

## HCF 文件格式

```
偏移   大小   字段
----   ----   ----
0      4      魔数: 'HCF\x1a'
4      2      版本号 (uint16 LE)
6      2      标志位 (编码器ID、压缩级别、是否有扩展)
8      2      CRC-16 (header 完整性校验)
10     2      符号数量 N (通常为 256)
12     N      比特长度表 (每个符号 1 字节，0=未出现)
12+N   8      原始大小 (uint64 LE)        ← 炸弹检测锚点
20+N   4      扩展数据长度 (可选)
24+N   E      扩展数据 (JSON，可插拔)
```

设计要点：
- **存比特长度而非频率表** — Canonical Huffman 标准做法，header 紧凑
- **扩展数据用 JSON** — 人和机器都可读，各插件自行定义 schema
- **original_size 天然防炸弹** — 无需额外校验字段

## 项目结构

```
hcompress/
├── hcompress/
│   ├── interfaces/      # 10 个 ABC 接口定义
│   ├── plugins/
│   │   ├── registry.py  # 插件自动发现与加载
│   │   ├── builtin/     # BombGuard 内置插件
│   │   └── sdk/         # 空操作基类 + 脚手架工具
│   ├── c_ext/           # C 加速模块
│   │   ├── _hcompress.c # C 源码
│   │   └── __init__.py  # ctypes 绑定（自动回退纯 Python）
│   ├── engine.py        # 压缩/解压总调度器
│   ├── canonical.py     # 哈夫曼树构建 & 规范编码
│   ├── bitstream.py     # 比特级读写
│   ├── checksum.py      # CRC-32 校验
│   ├── format.py        # HCF 文件头读写
│   ├── cli.py           # Click + Rich 命令行
│   └── gui.py           # tkinter 图形界面
├── demo/index.html      # 3D 架构 + ECharts 可视化演示
├── tests/               # 69 个单元测试
├── dist/                # 打包好的 .exe
├── hcompress.bat        # Windows 一键入口
└── 启动GUI.bat           # 双击启动 GUI
```

## 打包为独立 EXE

```bash
pip install pyinstaller
python -m PyInstaller --onefile --windowed \
  --name hcompress \
  --add-data "hcompress/c_ext/_hcompress.dll:." \
  --add-data "hcompress/plugins/builtin:plugins/builtin" \
  --collect-all rich --collect-all click \
  hcompress/launcher.py
```

输出：`dist/hcompress.exe`（约 36 MB，零依赖，拷到哪台 Windows 都能跑）。

## 开发

```bash
pip install -e ".[dev]"
pytest tests/ -v          # 69 个测试
python -m hcompress gui   # 启动 GUI
```

## 压缩效果速查

| 适合压缩 | 不适合压缩 |
|---|---|
| 🟢 纯文本 (.txt .md .log) | 🔴 已压缩文件 (.zip .rar .7z) |
| 🟢 源代码 (.py .c .js .html) | 🔴 图片 (.jpg .png .webp) |
| 🟢 未压缩位图 (.bmp) | 🔴 视频/音频 (.mp4 .mp3 .aac) |
| 🟢 3D 文本格式 (.obj .stl ASCII) | 🔴 加密/随机数据 |
| 🟡 未压缩 WAV 音频 | 🟡 二进制 3D (.stl binary .3ds) |

## 开源协议

MIT © Eric
