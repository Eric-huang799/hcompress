"""IMatchFinder — LZ-style dictionary matching interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Match:
    """A single back-reference match found in the input data."""

    distance: int   # how far back the match starts (1 = previous byte)
    length: int     # number of matching bytes (≥ 3 typically)
    pos: int        # position in *this* block where the match was found


class IMatchFinder(ABC):
    """
    Dictionary-based match finder for LZ77-family algorithms.

    Used when the entropy coder supports a hybrid LZ + Huffman mode
    (e.g. DEFLATE-style literal / length + distance coding).

    When no match finder is provided the engine operates in pure
    Huffman (literal-only) mode.

    Implementations:
        - HashChain  — simple, moderate speed / ratio trade-off.
        - BinaryTree — slower but finds optimal matches.
        - LZMA-style — large window, complex parsing (future).
    """

    @property
    @abstractmethod
    def window_size(self) -> int:
        """Maximum look-back window in bytes."""
        ...

    @abstractmethod
    def find_matches(self, data: bytes, pos: int) -> list[Match]:
        """
        Find all reasonable matches starting at `pos` within the window.

        The implementation may return multiple candidates; the caller
        (e.g. a lazy-parsing engine) selects the best one.
        """
        ...
