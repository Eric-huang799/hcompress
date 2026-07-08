"""BWTTransform — Burrows-Wheeler Transform plugin.

Data structure: suffix array (circular rotations sorted lexicographically).

The BWT reorders the input so that identical characters cluster together,
creating long runs of repeated bytes.  This makes Huffman + MTF dramatically
more effective on text data.

Format (stored in data stream, transparent to HCF header):
    [4 bytes: primary_index (uint32 big-endian)]  [n bytes: last_column]

The 4-byte header is unambiguous because the original data never needs
a 4-byte prefix — the BWT always outputs exactly n bytes for an n-byte
input plus the 4-byte primary_index.  Together with MTF, this forms the
bzip2-classic pipeline: BWT → MTF → Huffman.

Classic bzip2 pipeline:          Our plugin pipeline:
  BWT → MTF → RLE → Huffman        BWT → MTF → Huffman (canonical)
"""

from __future__ import annotations

import struct
from typing import ClassVar

from hcompress.interfaces.transform import ITransform
from hcompress.plugins.manifest import PluginMeta


class BWTTransform(ITransform):
    """Burrows-Wheeler Transform — suffix-array-based reordering.

    Forward:  build all cyclic rotations, sort by suffix, output
              primary_index + last_column.
    Reverse:  reconstruct via counting-sort–based LF-mapping (O(n) time,
              O(256) space).
    """

    name: str = "bwt"
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="BWTTransform",
        version="1.0.0",
        author="hcompress",
        description="Burrows-Wheeler变换 — 后缀数组排序，相同字符聚类，为MTF铺路",
        plugin_type="transform",
        priority=10,
    )

    _announced: bool = False

    # ── forward ─────────────────────────────────────────────────────────

    def forward(self, data: bytes) -> bytes:
        n = len(data)
        if n <= 1:
            self._notify()
            return struct.pack(">I", 0) + (data or b"")

        # Build suffix array via sort over doubled string.
        doubled = data + data
        indices = list(range(n))
        indices.sort(key=lambda i: doubled[i : i + n])

        primary_index = indices.index(0)
        last_column = bytes(doubled[i + n - 1] for i in indices)

        self._notify()
        return struct.pack(">I", primary_index) + last_column

    # ── reverse ─────────────────────────────────────────────────────────

    def reverse(self, data: bytes) -> bytes:
        if len(data) <= 4:
            return data[4:] if len(data) > 4 else (data or b"")

        primary_index = struct.unpack(">I", data[:4])[0]
        last_column = data[4:]
        n = len(last_column)

        if n == 0:
            return b""

        # --- counting sort → first column positions ---
        count = [0] * 256
        for b in last_column:
            count[b] += 1

        first_occ: dict[int, int] = {}
        cumsum = 0
        for b in range(256):
            if count[b]:
                first_occ[b] = cumsum
                cumsum += count[b]

        # --- build LF-mapping (transform vector T) ---
        occ_seen = [0] * 256
        T = [0] * n
        for i in range(n):
            b = last_column[i]
            T[i] = first_occ[b] + occ_seen[b]
            occ_seen[b] += 1

        # --- reconstruct original ---
        result = bytearray(n)
        row = primary_index
        for i in range(n - 1, -1, -1):
            result[i] = last_column[row]
            row = T[row]

        return bytes(result)

    # ── helpers ─────────────────────────────────────────────────────────

    def _notify(self) -> None:
        if not BWTTransform._announced:
            BWTTransform._announced = True
            print("[BWT] Burrows-Wheeler Transform 已启用 — 后缀数组聚类")
