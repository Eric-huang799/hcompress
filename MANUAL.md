# hcompress 操作手册

> Canonical Huffman 压缩工具 · v1 引擎 + v2 桌面端 · 全平台支持

---

## 目录

1. [快速开始](#1-快速开始)
2. [命令行使用](#2-命令行使用)
3. [GUI 桌面端 (v2)](#3-gui-桌面端-v2)
4. [压缩 & 解压格式](#4-压缩--解压格式)
5. [插件系统](#5-插件系统)
6. [炸弹检测 (BombGuard)](#6-炸弹检测-bombguard)
7. [文件夹归档](#7-文件夹归档)
8. [性能优化](#8-性能优化)
9. [插件开发](#9-插件开发)
10. [文件格式规范](#10-文件格式规范)
11. [常见问题](#11-常见问题)

---

## 1. 快速开始

### 安装 v1 引擎（命令行）

```bash
git clone https://github.com/Eric-huang799/hcompress.git
cd hcompress
pip install -e .
```

验证安装：

```bash
hcompress --version
# → hcompress, version 0.1.0
```

### 安装 v2 桌面端（图形界面）

[下载便携版](https://github.com/Eric-huang799/hcompress-v2/releases) → 解压 → 双击 `hcompress.exe`

> **前提**：需要本机已安装 Python 3.11+，并且 hcompress v1 已 `pip install -e .`

---

## 2. 命令行使用

### 压缩

```bash
# 基本压缩（输出到同目录，文件名为 原文件名.hcf）
hcompress c report.txt

# 指定输出路径
hcompress c report.txt -o D:\backup\report.txt.hcf

# 指定压缩级别 (0=最快 9=最优)
hcompress c bigfile.log --level 9

# 强制覆盖已存在的输出文件
hcompress c data.csv -o out.hcf -f
```

### 解压

```bash
# 解压 HCF 文件
hcompress d report.txt.hcf

# 解压到指定路径
hcompress d archive.hcf -o D:\restored\report.txt

# 强制覆盖
hcompress d archive.hcf -f
```

### 查看文件信息

```bash
hcompress info archive.hcf
```

输出示例：

```
         📦  HCF Info  —  archive.hcf
┌────────────────────┬──────────────────────────┐
│ Version            │ 1                        │
│ Compression level  │ 6                        │
│ Entropy coder      │ Canonical Huffman (id=0) │
│ Symbols used       │ 19 / 256                 │
│ Max code length    │ 6 bits                   │
│ Original size      │ 144.5 KB (148,000 bytes) │
│ Est. ratio         │ 50.4%  (-49.6%)          │
└────────────────────┴──────────────────────────┘
```

### 性能测试

```bash
hcompress bench bigfile.txt -n 10
```

### 其他命令

```bash
hcompress gui                    # 启动图形界面
hcompress plugin list            # 查看已加载插件
hcompress plugin new my-guard --type decompress-hook   # 生成插件模板
```

---

## 3. GUI 桌面端 (v2)

### 启动

双击 `hcompress.exe` 或桌面快捷方式。

### 界面概览

```
┌─────────┐ ┌──────────────────────────────────────────┐
│ 📦 压缩  │ │ 📂 点击选择输出目录  [📄添加] [📁文件夹] [⚡开始] [⚙️] │
│ 📂 解压  │ │                                           │
│ 📁 浏览器│ │  ┌─ 📦 拖拽文件或文件夹到此处 ──┐          │
│ 🔌 插件  │ │  └────────────────────────────────┘      │
│         │ │                                           │
│  🛡️Guard│ │  report.txt   1.2 MB  预计 ~48%   ✕      │
│         │ │  project/    15.4 MB  预计 ~52%   ✕      │
│         │ │                                           │
│         │ │  20.4 MB  │  11.8 MB  │  🛡️ Guard 启用   │
└─────────┘ └──────────────────────────────────────────┘
```

### 操作流程

#### 压缩文件

1. 点击左侧 **📦 压缩**
2. 点击 **📄 添加文件** 或 **📁 添加文件夹**，选择要压缩的内容
3. （可选）点击顶部路径栏，选择输出目录（默认同源文件目录）
4. 点击 **⚡ 开始压缩**
5. 等待完成，Toast 提示结果

#### 解压文件

1. 点击左侧 **📂 解压**
2. 点击 **📄 添加文件**，选择 `.hcf` 文件（或其他支持的格式）
3. 点击 **⚡ 开始解压**
4. 解压完成，输出文件在同目录下

> 如果文件是压缩炸弹，会弹出红色拦截窗口，提示膨胀比异常。

### 归档浏览器

1. 点击左侧 **📁 归档浏览器**
2. 点击 **📂 打开 HCF 文件**
3. 查看文件信息（大小、压缩率、符号数等）

### 插件管理

1. 点击左侧 **🔌 插件**
2. 查看已加载的插件列表
3. 每个插件有开关按钮，可单独启用/关闭
4. 插件出错会显示红色错误信息，不影响主程序

### 设置

1. 点击右上角 **⚙️**
2. 切换主题：☀️ 浅色 / 💻 跟随系统 / 🌙 深色
3. 调整默认压缩级别 (0-9)
4. 查看 BombGuard 状态

### 快捷键

| 快捷键 | 功能 |
|---|---|
| `F11` | 全屏 / 退出全屏 |
| `Esc` | 退出全屏 / 关闭弹窗 |

---

## 4. 压缩 & 解压格式

### 支持的压缩格式（输出）

| 格式 | 扩展名 | 说明 |
|---|---|---|
| **HCF** | `.hcf` | hcompress 原生格式，Canonical Huffman 编码 |

### 支持的解压格式（输入）

| 格式 | 扩展名 | 说明 |
|---|---|---|
| **HCF** | `.hcf` | 原生格式，含 BombGuard 炸弹检测 |
| **Gzip** | `.gz` | 单文件压缩 |
| **Bzip2** | `.bz2` | 单文件压缩 |
| **XZ / LZMA** | `.xz` | 单文件压缩 |
| **ZIP** | `.zip` | 多文件归档 |
| **TAR** | `.tar` `.tar.gz` `.tar.bz2` `.tar.xz` | 多文件归档 |

> 格式自动检测通过文件魔数（magic bytes），无需手动指定。

### 压缩率参考

| 文件类型 | 预计压缩率 | 说明 |
|---|---|---|
| `.txt` `.md` `.log` `.csv` `.json` `.py` `.c` `.html` | **~48%** | 文本类，哈夫曼最擅长 |
| `.bmp` `.wav` `.obj(ASCII)` | **~45%** | 未压缩格式 |
| `.stl(binary)` `.3ds` | **~85%** | 二进制但未熵编码 |
| `.png` `.jpg` `.mp4` `.zip` | **~98%** | 已压缩，几乎无效果 |
| 加密/随机数据 | **~100%** | 均匀分布，不可压缩 |

---

## 5. 插件系统

### 插件目录

```
hcompress/
└── hcompress/
    └── plugins/
        └── builtin/        ← 内置插件（默认加载）
            ├── bomb_guard.py
            └── formats/
                └── __init__.py
```

### 添加自定义插件

**方式一：放入内置目录**

将 `.py` 文件复制到 `hcompress/plugins/builtin/`，程序启动时自动加载。

**方式二：指定插件目录**

```bash
hcompress d archive.hcf --plugin-dir ./my-plugins/
```

### 生成插件模板

```bash
hcompress plugin new 我的插件名 --type decompress-hook
```

支持的插件类型：

| 类型 | 用途 |
|---|---|
| `decompress-hook` | 解压流程拦截（炸弹检测、日志等） |
| `compress-hook` | 压缩流程钩子 |
| `extension` | 万能扩展（加密、签名、元数据等） |
| `checksum` | 自定义校验算法 |
| `transform` | 数据变换（BWT、RLE 等） |

### 插件状态

| 状态 | 图标 | 说明 |
|---|---|---|
| 已启用 | 🟢 绿色 | 正常运行 |
| 已关闭 | ⚪ 灰色 | 用户关闭，不加载 |
| 启用失败 | 🔴 红色 + 错误信息 | 代码异常，已自动隔离 |

插件错误不会影响主程序运行。

---

## 6. 炸弹检测 (BombGuard)

### 原理

HCF 文件 header 中存储了 `original_size`（原始文件大小）。解压前读取 header 即可计算膨胀比：

```
膨胀比 = original_size ÷ 压缩文件实际大小

如果膨胀比 > 阈值 → 拒绝解压（疑似压缩炸弹）
```

### 默认配置

| 参数 | 默认值 | 说明 |
|---|---|---|
| 膨胀比阈值 | 100:1 | 压缩文件 1KB 声称解压出 >100KB 即拦截 |
| 递归深度限制 | 5 层 | 防止嵌套炸弹（.hcf 里面套 .hcf） |

### 关闭炸弹检测

```bash
hcompress d archive.hcf --no-bomb-guard
```

> ⚠️ 仅在信任文件来源时使用。

---

## 7. 文件夹归档

### 压缩文件夹

```bash
# CLI
hcompress c myproject/

# GUI
点击 📁 添加文件夹 → 选择目录 → 开始压缩
```

压缩后生成 `myproject.hcf`，内部包含完整目录结构和文件内容。

### 解压文件夹归档

```bash
hcompress d myproject.hcf -o ./restored/
```

自动重建目录树。

---

## 8. 性能优化

### C 扩展加速

hcompress 自带 C 扩展加速模块。编译后：

| 操作 | 纯 Python | C 扩展 | 加速比 |
|---|---|---|---|
| 编码 (530KB) | 385 ms | 88 ms | **4.4×** |
| 解码 (530KB) | 809 ms | 28 ms | **29.5×** |

### 编译 C 扩展

```bash
cd hcompress/hcompress/c_ext
gcc -shared -O3 -march=native -o _hcompress.dll _hcompress.c
```

编译后程序自动检测并启用加速。如 DLL 不存在则自动回退纯 Python。

### 大文件优化

- 使用 `--level 0-3` 提高速度（牺牲少量压缩率）
- 避免压缩已压缩格式的文件（.jpg .mp4 .zip 等）

---

## 9. 插件开发

### 快速开始

```bash
# 1. 生成模板
hcompress plugin new my-logger --type decompress-hook

# 2. 编辑生成的 .py 文件，只写你需要的方法
```

### 示例：自定义日志插件

```python
from hcompress.plugins.sdk import BaseDecompressHook

class MyLogger(BaseDecompressHook):
    def on_done(self, ctx, stats):
        print(f"解压完成！{stats.original_size} 字节")
```

### 示例：自定义炸弹检测阈值

```python
from hcompress.plugins.builtin.bomb_guard import BombGuardPlugin

class StrictGuard(BombGuardPlugin):
    def __init__(self):
        super().__init__(max_ratio=50)  # 更严格的 50:1 阈值
```

### 插件开发规则

1. 继承 SDK 基类（`BaseDecompressHook` / `BaseCompressHook` / `BaseExtension`）
2. 只 override 你需要的方法，其余自动 no-op
3. 插件出错会打印警告，不影响主流程
4. 放在 `plugins/builtin/` 或通过 `--plugin-dir` 指定

---

## 10. 文件格式规范

### HCF Header 结构

```
偏移   大小   字段
----   ----   ----
0      4      魔数: 'H' 'C' 'F' 0x1A
4      2      版本号 (uint16 LE, v1 = 0x0001)
6      2      标志位:
              bit 0:   有扩展数据
              bit 1-4: 压缩级别 (0-9)
              bit 5-7: 熵编码器 ID (0=Canonical Huffman)
              bit 8:   目录归档
8      2      CRC-16（header 完整性校验）
10     2      符号数量 N (典型值 256)
12     N      比特长度表（每个符号 1 字节，0 = 未出现）
12+N   8      原始文件大小 (uint64 LE)
20+N   4      扩展数据长度 E (仅 flags bit 0 置位时存在)
24+N   E      扩展数据 (JSON UTF-8)
────   ───    ──── header 结束 ────
...   ...     压缩后的比特流（补齐到字节边界）
```

### 归档格式（文件夹压缩时）

```
[4 bytes: path_len (uint32 LE)  |  path_len bytes: rel_path (UTF-8)  |  8 bytes: file_size (uint64 LE)  |  file_size bytes: content] × N
[4 bytes: 0x00000000]  ← 结束标记
```

---

## 11. 常见问题

### Q: 压缩后文件比原文件还大？

A: 正常现象。HCF header 固定 276 字节，加上小文件的哈夫曼编码效率不高。建议压缩 >1KB 的文件，或使用文件夹归档。

### Q: 解压时提示 "Header CRC-16 mismatch"？

A: 文件已损坏或被篡改。请重新获取原始文件。

### Q: 能解压 .rar 文件吗？

A: 目前不支持 RAR 格式（专利限制）。支持 gzip / bzip2 / xz / zip / tar。

### Q: 炸弹检测误拦了正常文件怎么办？

A: 使用 `--no-bomb-guard` 临时关闭。或调整阈值重新编译 BombGuard 插件。

### Q: macOS / Linux 能用吗？

A: v1 引擎跨平台。v2 桌面端目前只提供 Windows 版，Linux/macOS 可从源码构建：`npm install && npm run dist`

### Q: 如何更新？

```bash
# v1 引擎
cd hcompress && git pull && pip install -e .

# v2 桌面端
cd hcompress-v2 && git pull && npm install && npm run dist
```

---

## 附录

### 项目链接

| 项目 | 地址 |
|---|---|
| v1 引擎 (CLI + C扩展) | https://github.com/Eric-huang799/hcompress |
| v2 桌面端 (Electron) | https://github.com/Eric-huang799/hcompress-v2 |
| v2 Release 下载 | https://github.com/Eric-huang799/hcompress-v2/releases |

### 技术栈

| 层 | 技术 |
|---|---|
| 压缩引擎 | Python 3.11+ + C (GCC) |
| CLI | Click + Rich |
| GUI v1 | tkinter |
| GUI v2 | Electron + React + TypeScript + Vite |
| 插件系统 | Python ABC + 动态导入 |
| 测试 | pytest (69 个测试) |
