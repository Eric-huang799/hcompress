"""ITransform — reversible data transform interface."""

from abc import ABC, abstractmethod


class ITransform(ABC):
    """
    Reversible data transform applied before frequency analysis.

    Transforms are applied in order (a chain) to the raw data before
    frequency counting and entropy coding.  During decompression the
    chain is reversed so each transform's reverse() is called in the
    opposite order.

    Classic examples:
        - BWT (Burrows–Wheeler Transform) followed by MTF → makes text highly compressible.
        - RLE (Run-Length Encoding) → collapses long runs of identical bytes.
        - Delta encoding → stores differences; great for audio / sensor data.
    """

    name: str

    @abstractmethod
    def forward(self, data: bytes) -> bytes:
        """Apply the transform before compression."""
        ...

    @abstractmethod
    def reverse(self, data: bytes) -> bytes:
        """Reverse the transform after decompression."""
        ...
