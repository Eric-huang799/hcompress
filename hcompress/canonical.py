"""Canonical Huffman codec — tree building, code assignment, decode tables."""

from __future__ import annotations

import heapq
from collections import defaultdict

# ── constants ────────────────────────────────────────────────────────────────

ALPHABET_SIZE = 256       # byte-level symbols
MAX_CODE_LENGTH = 255     # theoretical max for 256-symbol alphabet


# ── frequency ────────────────────────────────────────────────────────────────


def freq_table(data: bytes) -> list[int]:
    """Return 256-element frequency list for *data*."""
    freq: list[int] = [0] * ALPHABET_SIZE
    for byte in data:
        freq[byte] += 1
    return freq


# ── tree → bit-lengths ───────────────────────────────────────────────────────


def _build_bit_lengths(freq: list[int]) -> list[int]:
    heap: list[tuple[int, int, object]] = []
    for symbol, weight in enumerate(freq):
        if weight > 0:
            # Leaf: (weight, unique_id, payload)
            # payload for leaf = symbol (int)
            heapq.heappush(heap, (weight, symbol, symbol))

    if len(heap) == 0:
        return [0] * ALPHABET_SIZE

    # Edge case: single symbol
    if len(heap) == 1:
        bl = [0] * ALPHABET_SIZE
        bl[heap[0][2]] = 1
        return bl

    # Build tree
    _next_id = ALPHABET_SIZE  # IDs for internal nodes start beyond symbols
    while len(heap) > 1:
        w1, _id1, left = heapq.heappop(heap)
        w2, _id2, right = heapq.heappop(heap)
        heapq.heappush(heap, (w1 + w2, _next_id, (left, right)))
        _next_id += 1

    # Walk tree, assign depths
    bit_lengths: list[int] = [0] * ALPHABET_SIZE

    def _walk(node: object, depth: int) -> None:
        if isinstance(node, int):
            # Leaf — node is the symbol
            bit_lengths[node] = depth
        else:
            left, right = node
            _walk(left, depth + 1)
            _walk(right, depth + 1)

    _walk(heap[0][2], 0)
    return bit_lengths


# ── canonical codes ──────────────────────────────────────────────────────────


def canonical_from_freq(freq: list[int]) -> tuple[list[int], list[int]]:
    """Build canonical Huffman codes from frequency table.

    Returns:
        (codes, bit_lengths) — both 256-element lists.
    """
    bit_lengths = _build_bit_lengths(freq)

    # Group symbols by bit-length, sorted by symbol within each length
    symbols_by_len: dict[int, list[int]] = defaultdict(list)
    for sym, bl in enumerate(bit_lengths):
        if bl > 0:
            symbols_by_len[bl].append(sym)
    for bl in symbols_by_len:
        symbols_by_len[bl].sort()  # smaller symbol → smaller code

    # Assign canonical codes
    codes: list[int] = [0] * ALPHABET_SIZE
    code = 0
    prev_len = 0

    for length in sorted(symbols_by_len):
        # Shift code left when moving to a longer bit-length
        code <<= (length - prev_len)
        for sym in symbols_by_len[length]:
            codes[sym] = code
            code += 1
        prev_len = length

    return codes, bit_lengths


# ── decode table ─────────────────────────────────────────────────────────────


def build_decode_table(
    bit_lengths: list[int],
) -> tuple[
    list[int],
    list[int],
    list[list[int]],
    int,
]:
    """Build fast-decode structures from bit-lengths."""
    max_len = max(bit_lengths) if any(bit_lengths) else 0
    return (*_build_decode_aux(bit_lengths, max_len), max_len)


def _build_decode_aux(
    bit_lengths: list[int], max_len: int
) -> tuple[list[int], list[int], list[list[int]]]:

    # 1. Count symbols per length
    bl_count = [0] * (max_len + 1)
    for bl in bit_lengths:
        if bl > 0:
            bl_count[bl] += 1

    # 2. Compute base_code for each length (canonical first code)
    base_code = [0] * (max_len + 1)
    code = 0
    for length in range(1, max_len + 1):
        code = (code + bl_count[length - 1]) << 1 if length > 1 else 0
        base_code[length] = code

    # 3. Assign codes to symbols and group by length
    next_code = base_code.copy()
    symbols_by_len: list[list[int]] = [[] for _ in range(max_len + 1)]
    for sym in range(ALPHABET_SIZE):
        bl = bit_lengths[sym]
        if bl > 0:
            symbols_by_len[bl].append(sym)  # appended in symbol order

    # Sort each group by assigned code
    # Since we process in symbol order and next_code increments by 1,
    # within a length group the symbols are already in code order.

    # Compute base_symbol offset
    symbol_offset = [0] * (max_len + 1)
    offset = 0
    for length in range(1, max_len + 1):
        symbol_offset[length] = offset
        offset += len(symbols_by_len[length])

    return base_code, symbol_offset, symbols_by_len


def decode_symbol(
    reader: "BitReader",
    base_code: list[int],
    symbol_offset: list[int],
    symbols_by_len: list[list[int]],
    max_len: int,
) -> int:
    """Decode a single symbol from *reader* using canonical tables."""
    value = 0
    for length in range(1, max_len + 1):
        value = (value << 1) | reader.read_bit()
        count = len(symbols_by_len[length])
        if count == 0:
            continue
        offset = value - base_code[length]
        if 0 <= offset < count:
            return symbols_by_len[length][offset]
    raise ValueError(
        f"No matching Huffman code for accumulated bits 0x{value:x}"
    )


# ── encode helpers ───────────────────────────────────────────────────────────


def encode_data(
    writer: "BitWriter",
    data: bytes,
    codes: list[int],
    bit_lengths: list[int],
) -> None:
    """Encode *data* using canonical codes, write to *writer*."""
    for byte in data:
        code = codes[byte]
        nbits = bit_lengths[byte]
        if nbits == 0:
            raise ValueError(
                f"Symbol 0x{byte:02x} has no assigned code "
                f"(missing from frequency table)"
            )
        writer.write_bits(code, nbits)
