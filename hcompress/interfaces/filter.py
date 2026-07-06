"""IFilter — pre-processing filter interface."""

from abc import ABC, abstractmethod


class IFilter(ABC):
    """
    Pre-processing filter.

    Unlike ITransform (which is purely a mathematical bijection), a Filter
    may carry side-channel information (e.g. a dictionary table, a predictor
    state) that must be serialised into the HCF extension_data so the decoder
    can reconstruct it.

    Filters are applied *before* frequency analysis during compression.
    During decompression they are applied in reverse order after decoding.

    Examples:
        - PNG-style row predictor filters (None/Sub/Up/Average/Paeth).
        - Delta encoding for PCM audio channels.
        - Dictionary-based pre-substitution (common substrings → short tokens).
    """

    filter_id: int

    @abstractmethod
    def apply(self, data: bytes) -> bytes:
        """Apply filter before compression."""
        ...

    @abstractmethod
    def revert(self, data: bytes) -> bytes:
        """Revert filter after decompression."""
        ...
