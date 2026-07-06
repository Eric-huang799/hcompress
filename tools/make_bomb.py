"""压缩包炸弹生成器 — 仅用于测试 BombGuard 检测能力。

用法:
    python tools/make_bomb.py <输入文件> <输出.hcf> [--size 10GB] [--ratio 1000000]

示例:
    python tools/make_bomb.py demo.txt bomb.hcf --size 10GB
    python tools/make_bomb.py demo.txt bomb.hcf --ratio 1000000
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hcompress.format import MAGIC, _crc16, FLAG_HAS_EXTENSION
from hcompress.engine import compress, CompressConfig


def parse_size(s: str) -> int:
    """Parse human-readable size like '10GB', '500MB', '100KB'."""
    s = s.strip().upper()
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    for unit, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if s.endswith(unit):
            return int(float(s[:-len(unit)]) * mult)
    return int(s)


def make_bomb(input_path: str, output_path: str, fake_size: int) -> None:
    """Create a bomb .hcf file with a faked original_size."""
    import tempfile

    # Step 1: Compress normally
    tmp = tempfile.mktemp(suffix=".hcf")
    compress(input_path, tmp, CompressConfig(level=6))

    # Step 2: Read the HCF, patch original_size
    with open(tmp, "rb") as f:
        data = bytearray(f.read())
    os.unlink(tmp)

    real_original = struct.unpack_from("<Q", data, 268)[0]
    real_filesize = len(data)

    # Step 3: Overwrite original_size at offset 268 (8 bytes, uint64 LE)
    struct.pack_into("<Q", data, 268, fake_size)

    # Step 4: Recalculate CRC-16 over header
    # Header with extension data? Check flags
    flags = struct.unpack_from("<H", data, 6)[0]
    if flags & FLAG_HAS_EXTENSION:
        ext_len = struct.unpack_from("<I", data, 276)[0]
        header_len = 280 + ext_len  # 4(magic)+2(ver)+2(flags)+2(crc)+2(N)+256(bl)+8(orig)+4(extlen)+ext
    else:
        header_len = 276

    crc_input = bytes(data[:8]) + bytes(data[10:header_len])
    new_crc = _crc16(crc_input)
    struct.pack_into("<H", data, 8, new_crc)

    # Step 5: Write bomb
    with open(output_path, "wb") as f:
        f.write(data)

    ratio = fake_size / real_filesize
    print("💣 炸弹文件已生成！")
    print(f"   文件: {output_path}")
    print(f"   实际大小: {real_filesize:,} 字节 ({real_filesize/1024:.1f} KB)")
    print(f"   原始数据: {real_original:,} 字节 (真实)")
    print(f"   伪造声明: {fake_size:,} 字节 ({fake_size/1024**3:.1f} GB)")
    print(f"   膨胀比:   {ratio:,.0f}:1")
    print(f"   阈值:     100:1")
    print(f"   预期结果: {'💥 应该被 BombGuard 拦截' if ratio > 100 else '⚠️ 膨胀比不够高，可能不会被拦'}")
    print()
    print("测试命令:")
    print(f"   hcompress d {output_path} -o /tmp/out.bin")
    print(f"   hcompress d {output_path} -o /tmp/out.bin --no-bomb-guard  (强制解压)")


def main():
    parser = argparse.ArgumentParser(
        description="hcompress 炸弹文件生成器 — 测试 BombGuard 用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/make_bomb.py README.md bomb.hcf --size 10GB
  python tools/make_bomb.py README.md bomb.hcf --ratio 500000
        """,
    )
    parser.add_argument("input", help="任意输入文件（用于生成压缩数据）")
    parser.add_argument("output", help="输出的炸弹 .hcf 文件路径")
    parser.add_argument(
        "--size", default="100GB",
        help="伪造的原始文件大小 (如 10GB, 500MB, 100KB)，默认 100GB",
    )
    parser.add_argument(
        "--ratio", type=int, default=0,
        help="直接指定膨胀比 (如 1000000)，覆盖 --size",
    )
    args = parser.parse_args()

    fake_size = parse_size(args.size)
    if args.ratio > 0:
        # Calculate needed fake_size from ratio
        import tempfile
        tmp = tempfile.mktemp(suffix=".hcf")
        compress(args.input, tmp, CompressConfig(level=6))
        real_size = os.path.getsize(tmp)
        os.unlink(tmp)
        fake_size = real_size * args.ratio
        print(f"从膨胀比计算: {real_size} × {args.ratio} = {fake_size:,} 字节 ({fake_size/1024**3:.1f} GB)")

    make_bomb(args.input, args.output, fake_size)


if __name__ == "__main__":
    main()
