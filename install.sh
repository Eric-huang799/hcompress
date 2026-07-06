#!/bin/bash
# hcompress Ubuntu/Linux 一键安装脚本
set -e

echo ""
echo "  hcompress — Canonical Huffman 压缩工具"
echo "  Ubuntu / Linux 一键安装"
echo "  ========================================="

# 1. System deps
echo "[1/4] 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-tk gcc make curl

# 2. Python deps
echo "[2/4] 安装 Python 依赖..."
pip3 install --user click rich py7zr rarfile zstandard brotli lz4

# 3. Compile C extension
echo "[3/4] 编译 C 扩展加速..."
cd "$(dirname "$0")/hcompress/c_ext"
gcc -shared -O3 -fPIC -o _hcompress.so _hcompress.c
echo "C extension compiled: $(ls -la _hcompress.so | awk '{print $5}') bytes"

# 4. Install
echo "[4/4] 安装 hcompress..."
cd "$(dirname "$0")"
pip3 install --user -e .

echo ""
echo "  ✅ 安装完成！"
echo ""
echo "  用法:"
echo "    hcompress c 文件.txt       # 压缩"
echo "    hcompress d 文件.hcf       # 解压 HCF"
echo "    hcompress d 文件.zip       # 解压 ZIP/7z/RAR/gz/..."
echo "    hcompress gui              # 启动 GUI"
echo "    hcompress info 文件.hcf    # 查看文件信息"
echo ""
