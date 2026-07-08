"""MTFTransform — Move-to-Front Transform plugin.

Data structure: self-organising list (Move-to-Front).

After BWT clusters identical characters together, MTF converts each run
of repeated bytes into a stream of small integers (mostly zeros).  This
creates an ideal input for Huffman encoding because the frequency
distribution becomes extremely skewed (0 dominates).

The alphabet is a simple bytearray of 256 entries (0–255).  Each input
byte's position in the alphabet is emitted, then the byte is moved to
position 0.  Access is O(1) per byte via a position-lookup table.

Format: n bytes in → n bytes out (perfect bijection, zero overhead).
"""

from __future__ import annotations

from typing import ClassVar

from hcompress.interfaces.transform import ITransform
from hcompress.plugins.manifest import PluginMeta


class MTFTransform(ITransform):
    """Move-to-Front — self-organising-list transform.

    Forward:  for each input byte, output its index in the alphabet,
              then move the byte to the front.
    Reverse:  for each index, output the byte at that position in the
              alphabet, then move it to the front.
    """

    name: str = "mtf"
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="MTFTransform",
        version="1.0.0",
        author="hcompress",
        description="自组织Move-to-Front列表 — 连续相同字符转小整数，配合BWT大幅提升压缩率",
        plugin_type="transform",
        priority=20,
    )

    _announced: bool = False

    # ── forward ─────────────────────────────────────────────────────────

    def forward(self, data: bytes) -> bytes:
        if not data:
            self._notify()
            return b""

        alphabet = bytearray(range(256))
        pos_tbl = list(range(256))  # pos_tbl[byte] = position in alphabet

        result = bytearray(len(data))
        for idx, btn in enumerate(data):
            b = btn
            p = pos_tbl[b]
            result[idx] = p

            if p == 0:
                continue

            # Move b to front: shift positions 0..p-1 right by one
            moved = alphabet[p]
            for j in range(p, 0, -1):
                alphabet[j] = alphabet[j - 1]
                pos_tbl[alphabet[j]] = j
            alphabet[0] = moved
            pos_tbl[moved] = 0

        self._notify()
        return bytes(result)

    # ── reverse ─────────────────────────────────────────────────────────

    def reverse(self, data: bytes) -> bytes:
        if not data:
            return b""

        alphabet = bytearray(range(256))
        pos_tbl = list(range(256))

        result = bytearray(len(data))
        for idx, ptn in enumerate(data):
            p = ptn
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

    # ── helpers ─────────────────────────────────────────────────────────

    def _notify(self) -> None:
        if not MTFTransform._announced:
            MTFTransform._announced = True
            print("[MTF] Move-to-Front Transform 已启用 — 自组织列表")
