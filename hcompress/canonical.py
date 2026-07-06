"""Canonical Huffman codec — tree building, code assignment, decode tables."""

from __future__ import annotations

import heapq
from collections import defaultdict

# ── constants ────────────────────────────────────────────────────────────────

ALPHABET_SIZE = 256       # byte-level symbols
MAX_CODE_LENGTH = 255     # theoretical max for 256-symbol alphabet


# ── frequency ────────────────────────────────────────────────────────────────


def freq_table(data: bytes) -> list[int]:
    """Count symbol frequencies in *data*.

    Returns a 256-element list where ``freq[s]`` is the number of
    occurrences of byte value ``s``.  Symbols that never appear have
    a frequency of 0.
    """
    freq: list[int] = [0] * ALPHABET_SIZE
    for byte in data:
        freq[byte] += 1
    return freq


# ── tree → bit-lengths ───────────────────────────────────────────────────────


def _build_bit_lengths(freq: list[int]) -> list[int]:
    """Build Huffman tree from frequencies and return bit-length per symbol.

    Uses the standard min-heap algorithm.  Symbols with freq == 0 get
    bit-length 0 (i.e. they are absent from the stream).
    """
    # Collect leaf nodes: (weight, symbol)
    heap: list[tuple[int, int, object]] = []
    for symbol, weight in enumerate(freq):
        if weight > 0:
            # Leaf: (weight, unique_id, payload)
            # payload for leaf = symbol (int)
            heapq.heappush(heap, (weight, symbol, symbol))

    if len(heap) == 0:
        return [0] * ALPHABET_SIZE

    # Edge case: single symbol — give it code length 1
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
    """Build canonical Huffman codes from a frequency table.

    Returns:
        (codes, bit_lengths) — both 256-element lists.
        ``codes[s]`` is the canonical codeword (uint32, LSB-aligned).
        ``bit_lengths[s]`` is the number of bits in that codeword
        (0 = symbol not present).
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
    list[int],           # base_code[length] — first canonical code for this length
    list[int],           # symbol_offset[length] — index into symbols_by_len flat list
    list[list[int]],     # symbols_by_len[length] — symbols with this length, ordered by code
    int,                 # max_code_length
]:
    """Build fast-decode structures from bit-lengths.

    Returns structures that :func:`decode_symbol` uses for O(1)-per-bit
    symbol resolution.

    See Also:
        :func:`decode_symbol` for the actual per-bit decode loop.
    """
    max_len = max(bit_lengths) if any(bit_lengths) else 0
    return (*_build_decode_aux(bit_lengths, max_len), max_len)


def _build_decode_aux(
    bit_lengths: list[int], max_len: int
) -> tuple[list[int], list[int], list[list[int]]]:
    """Auxiliary: construct decode structures from bit_lengths."""

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
    # (Canonical property: within a length, codes increase with symbol.)

    # Compute base_symbol offset
    symbol_offset = [0] * (max_len + 1)
    offset = 0
    for length in range(1, max_len + 1):
        symbol_offset[length] = offset
        offset += len(symbols_by_len[length])

    return base_code, symbol_offset, symbols_by_len


def decode_symbol(
    reader: "BitReader",                 # noqa: F821  — forward ref
    base_code: list[int],
    symbol_offset: list[int],
    symbols_by_len: list[list[int]],
    max_len: int,
) -> int:
    """Decode a single symbol from *reader* using the canonical tables.

    Args:
        reader: BitReader positioned at compressed data.
        base_code: First canonical code for each bit-length.
        symbol_offset: Cumulative symbol index offset per length.
        symbols_by_len: Symbols grouped by bit-length (ordered by code).
        max_len: Maximum code length in bits.

    Returns:
        The decoded symbol (0–255).

    Raises:
        EOFError: unexpected end of stream.
        ValueError: bit sequence doesn't match any code (corrupt data).
    """
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
    writer: "BitWriter",                 # noqa: F821  — forward ref
    data: bytes,
    codes: list[int],
    bit_lengths: list[int],
) -> None:
    """Encode *data* using canonical Huffman codes and write to *writer*.

    Args:
        writer: BitWriter to receive the compressed bitstream.
        data: Raw bytes to encode.
        codes: 256-element canonical code table.
        bit_lengths: 256-element bit-length table.
    """
    for byte in data:
        code = codes[byte]
        nbits = bit_lengths[byte]
        if nbits == 0:
            raise ValueError(
                f"Symbol 0x{byte:02x} has no assigned code "
                f"(missing from frequency table)"
            )
        writer.write_bits(code, nbits)
