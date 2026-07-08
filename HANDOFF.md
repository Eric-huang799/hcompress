# hcompress 开发交接文档

> 写给接力的 Agent：项目全貌、代码位置、构建流程、优化方向
> 最后更新: 2026-07-06

---

## 一、项目架构

```
┌─────────────────────────────────────────────────┐
│              hcompress 全平台架构                 │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────┐   ┌──────────────┐   ┌──────────┐ │
│  │ v2 桌面   │   │  v1 引擎      │   │ Android  │ │
│  │ Electron  │──▶│  Python + C   │   │  Kotlin  │ │
│  │ React+TS  │   │  (被 v2 调用)  │   │  原生 APK │ │
│  └──────────┘   └──────┬───────┘   └──────────┘ │
│                        │                         │
│                 ┌──────▼───────┐                 │
│                 │  插件系统     │                 │
│                 │  10 ABC 接口  │                 │
│                 │  + GitHub商店 │                 │
│                 └──────────────┘                 │
└─────────────────────────────────────────────────┘
```

**v2 依赖 v1**：v2 Electron 通过 `spawn("python", ["-m", "hcompress", ...])` 调 v1 引擎。v2 是纯前端，压缩逻辑全在 v1。

---

## 二、代码位置速查

### v1 引擎 (`C:\Users\lenovo\hcompress\`)

| 文件 | 职责 |
|---|---|
| `hcompress/engine.py` | 压缩/解压总调度器，hook 链编排，合并 registry |
| `hcompress/canonical.py` | 哈夫曼树构建 + 规范编码 + 解码查表 |
| `hcompress/bitstream.py` | BitWriter / BitReader（MSB first, 字节内 LSB first） |
| `hcompress/format.py` | HCF header 读写（魔数/版本/CRC-16/bit-lengths） |
| `hcompress/checksum.py` | CRC-32 (0xEDB88320, 表驱动) |
| `hcompress/archiver.py` | 文件夹打包/解包（tar 风格格式） |
| `hcompress/parallel.py` | ProcessPoolExecutor 多进程并行压缩 |
| `hcompress/cli.py` | Click + Rich CLI（c/d/info/bench/gui/tui/plugin） |
| `hcompress/tui.py` | Textual 终端 UI（DirectoryTree 文件浏览器） |
| `hcompress/gui.py` | tkinter GUI |
| `hcompress/c_ext/_hcompress.c` | C 加速：编码/解码/CRC32 |
| `hcompress/c_ext/__init__.py` | ctypes 绑定 + 自动回退纯 Python |
| `hcompress/interfaces/` | 10 个 ABC 接口 + IExtension 万能扩展 |
| `hcompress/plugins/registry.py` | PluginRegistry：目录扫描 → import → 分类注册 |
| `hcompress/plugins/sdk/` | No-op Base 类 + 脚手架生成 |
| `hcompress/plugins/builtin/bomb_guard.py` | BombGuard 炸弹检测（100:1 阈值） |
| `hcompress/plugins/builtin/formats/` | 13 种格式解压 |
| `tests/` | 69 个 pytest 测试 |

### v2 桌面端 (`C:\Users\lenovo\hcompress-v2\`)

| 文件 | 职责 |
|---|---|
| `src/App.tsx` | React 主界面（全部组件在一个文件） |
| `src/styles/theme.css` | CSS 变量三主题（浅/深/系统） |
| `src/hooks/useTheme.ts` | 主题持久化 localStorage |
| `electron/main.cjs` | Electron 主进程：窗口 + findPython + runPython + IPC |
| `electron/preload.cjs` | contextBridge API（compress/decompress/hcfInfo/openFile/openDir/openPluginDir/listPlugins） |
| `build.cjs` | 手动打包脚本（解压 Electron → 复制文件 → 出便携版） |
| `public/icon.*` | 应用图标 |

### Android (`C:\Users\lenovo\hcompress-android\`)

| 文件 | 职责 |
|---|---|
| `app/src/main/java/.../engine/HuffmanEngine.kt` | 纯 Kotlin 哈夫曼引擎 |
| `app/src/main/java/.../engine/HcompressJNI.kt` | JNI 桥接（优雅降级） |
| `app/src/main/java/.../ui/MainActivity.kt` | Material 3 界面（程序化 UI） |
| `app/src/main/java/.../plugin/PluginManager.kt` | GitHub Releases 插件下载 |
| `app/src/main/AndroidManifest.xml` | 清单 |
| `app/build.gradle.kts` | 构建配置（compileSdk=34, minSdk=26） |
| `build.gradle.kts` | 根构建（Kotlin 2.0.21 + AGP 8.2.0） |

---

## 三、构建命令

### v1 Windows EXE
```bash
cd C:\Users\lenovo\hcompress
python -m PyInstaller --onefile --windowed --name hcompress \
  --add-data "hcompress/c_ext/_hcompress.dll:." \
  --add-data "hcompress/plugins/builtin:plugins/builtin" \
  --exclude-module PyQt5 --exclude-module PyQt6 \
  --exclude-module PySide2 --exclude-module PySide6 \
  --exclude-module matplotlib --exclude-module numpy \
  --exclude-module pygame \
  --collect-all rich --collect-all click \
  --hidden-import tkinter --hidden-import ctypes \
  hcompress/launcher.py
```
> 输出: `dist/hcompress.exe` (~36 MB)

### v2 Electron 桌面
```bash
cd C:\Users\lenovo\hcompress-v2
npm run dist    # = npm run build && node build.cjs
```
> 输出: `release/win-unpacked/hcompress.exe` (~338 MB 含 Chromium)

### Android APK
```bash
conda activate android-build   # JDK 17
export ANDROID_HOME=/c/Android
export JAVA_HOME=/c/Users/lenovo/.conda/envs/android-build/Library
cd C:\Users\lenovo\hcompress-android
/tmp/gradle-8.12/bin/gradle --no-daemon assembleDebug
```
> 输出: `app/build/outputs/apk/debug/app-debug.apk` (~6.3 MB)

### Linux C 扩展
```bash
cd hcompress/c_ext
gcc -shared -O3 -fPIC -o _hcompress.so _hcompress.c
```

---

## 四、关键设计决策

| 决策 | 选择 | 原因 |
|---|---|---|
| v2 调 v1 | Electron spawn Python CLI | 复用引擎，前后端分离 |
| HCF 存 bit-lengths | 不是完整哈夫曼树 | header 固定 256B，紧凑 |
| BombGuard 检测点 | `on_header_read` | 只读 276B header，零 IO |
| 炸弹阈值 | 100:1 | 正常压缩率 ~50%，100 倍绝无可疑 |
| C 扩展回退 | ctypes 加载失败 → 纯 Python | 无 .dll/.so 也能跑 |
| Android 引擎 | 纯 Kotlin（非 NDK） | 避免 NDK 编译复杂度 |
| Android JNI | `try { loadLibrary } catch` | .so 不存在时优雅降级 |
| Ubuntu pip | `--break-system-packages` | PEP 668 限制 |
| 插件注册 | `type(obj).__name__` 字符串匹配 | 避免跨 import 的 isinstance 问题 |

---

## 五、已知问题 & 优化方向

### 待优化
1. **v2 输出路径**：解压非 HCF 文件时输出命名逻辑（`_解压` 后缀）需统一
2. **v2 文件大小**：添加文件后 size 显示为 0（没有通过 IPC 获取文件信息）
3. **Android 多格式**：目前只支持 HCF，多格式解压需要移植 formats.py 逻辑到 Kotlin
4. **Android 并行**：纯 Kotlin 引擎无多线程加速
5. **v1 C 扩展瓶颈**：频率分析和树构建仍在 Python（占压缩时间 68%）
6. **v2 打包体积**：338MB 含完整 Chromium，可以用 Electron ASAR 压缩
7. **测试覆盖**：多格式解压、并行压缩无测试
8. **错误处理**：`_safe_call` 吞噬异常太激进，调试困难
9. **插件热加载**：v2 文件监听器已做，但 Python 端需重启才生效
10. **Linux v2**：Electron 可编译 Linux 版但未做（v1 TUI 已覆盖）

### 注意事项
- **不要提交** `tools/make_bomb.py` 到 GitHub（安全原因，已在 .gitignore）
- **不要提交** `_hcompress.dll` / `_hcompress.so`（.gitignore 已排除，但 Linux 版 force add 了一个）
- Windows PATH 里没有 `C:\Users\lenovo\AppData\Roaming\Python\Python312\Scripts`，pip 装的东西可能找不到
- `C:\ProgramData\anaconda3` 和 `C:\Users\lenovo\AppData\Roaming\Python\Python312` 两个 Python 共存，注意区分

---

## 六、GitHub 仓库

| 仓库 | 地址 |
|---|---|
| v1 引擎 | https://github.com/Eric-huang799/hcompress |
| v2 桌面 | https://github.com/Eric-huang799/hcompress-v2 |
| Android | https://github.com/Eric-huang799/hcompress-android |
| 插件商店 | https://github.com/Eric-huang799/hcompress-plugins |

---

## 七、快速启动

```bash
# Windows - v1 引擎
cd C:\Users\lenovo\hcompress
pip install -e .
hcompress c file.txt

# Windows - v2 桌面
# 双击 C:\Users\lenovo\Desktop\hcompress.lnk

# Ubuntu - TUI
cd ~/hcompress
GIT_SSL_NO_VERIFY=1 git pull
python3 -m hcompress tui

# Android
# 安装 C:\Users\lenovo\Desktop\hcompress.apk
```
