"""BwtMtfTransform — combined BWT + MTF bidirectional transform (BWT→MTF forward, MTF⁻¹→BWT⁻¹ reverse)."""

from __future__ import annotations

import struct
from typing import ClassVar

from hcompress.interfaces.transform import ITransform
from hcompress.plugins.manifest import PluginMeta


class BwtMtfTransform(ITransform):
    """BWT + MTF combined transform: forward BWT→MTF, reverse MTF⁻¹→BWT⁻¹."""

    name: str = "bwt_mtf"
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="BwtMtfTransform",
        version="1.0.0",
        author="hcompress",
        description="BWT+MTF联合变换 — 后缀数组聚类后自组织列表转小整数，大幅提升Huffman压缩率",
        plugin_type="transform",
        priority=10,
    )

    _announced: bool = False

    # ── forward: BWT → MTF ─────────────────────────────────────────────

    def forward(self, data: bytes) -> bytes:
        self._notify()
        data = self._bwt_forward(data)
        data = self._mtf_forward(data)
        return data

    # ── reverse: MTF⁻¹ → BWT⁻¹ ─────────────────────────────────────────

    def reverse(self, data: bytes) -> bytes:
        data = self._mtf_reverse(data)
        data = self._bwt_reverse(data)
        return data

    # ── BWT ──────────────────────────────────────────────────────────

    @staticmethod
    def _bwt_forward(data: bytes) -> bytes:
        n = len(data)
        if n <= 1:
            return struct.pack(">I", 0) + (data or b"")

        doubled = data + data
        indices = list(range(n))
        indices.sort(key=lambda i: doubled[i:i + n])
        primary_index = indices.index(0)
        last_column = bytes(doubled[i + n - 1] for i in indices)
        return struct.pack(">I", primary_index) + last_column

    @staticmethod
    def _bwt_reverse(data: bytes) -> bytes:
        if len(data) <= 4:
            return data[4:] if len(data) > 4 else (data or b"")

        primary_index = struct.unpack(">I", data[:4])[0]
        last_column = data[4:]
        n = len(last_column)
        if n == 0:
            return b""

        count = [0] * 256
        for b in last_column:
            count[b] += 1

        first_occ: dict[int, int] = {}
        cumsum = 0
        for b in range(256):
            if count[b]:
                first_occ[b] = cumsum
                cumsum += count[b]

        occ_seen = [0] * 256
        T = [0] * n
        for i in range(n):
            b = last_column[i]
            T[i] = first_occ[b] + occ_seen[b]
            occ_seen[b] += 1

        result = bytearray(n)
        row = primary_index
        for i in range(n - 1, -1, -1):
            result[i] = last_column[row]
            row = T[row]
        return bytes(result)

    # ── MTF ──────────────────────────────────────────────────────────

    @staticmethod
    def _mtf_forward(data: bytes) -> bytes:
        if not data:
            return b""
        alphabet = bytearray(range(256))
        pos_tbl = list(range(256))
        result = bytearray(len(data))
        for idx, b in enumerate(data):
            p = pos_tbl[b]
            result[idx] = p
            if p == 0:
                continue
            moved = alphabet[p]
            for j in range(p, 0, -1):
                alphabet[j] = alphabet[j - 1]
                pos_tbl[alphabet[j]] = j
            alphabet[0] = moved
            pos_tbl[moved] = 0
        return bytes(result)

    @staticmethod
    def _mtf_reverse(data: bytes) -> bytes:
        if not data:
            return b""
        alphabet = bytearray(range(256))
        pos_tbl = list(range(256))
        result = bytearray(len(data))
        for idx, p in enumerate(data):
            b = alphabet[p]
            result[idx] = b
            if p == 0:
                continue
            moved = alphabet[p]
            for j in range(p, 0, -1):
                alphabet[j] = alphabet[j - 1]
                pos_tbl[alphabet[j]] = j
            alphabet[0] = moved
            pos_tbl[moved] = 0
        return bytes(result)

    # ── helpers ──────────────────────────────────────────────────────

    def _notify(self) -> None:
        if not BwtMtfTransform._announced:
            BwtMtfTransform._announced = True
            print("[BwtMtf] BWT+MTF 联合变换已启用 — 后缀数组 → 自组织列表")
