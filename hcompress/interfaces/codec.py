"""IEntropyCodec — entropy coding algorithm interface."""

from abc import ABC, abstractmethod


class IEntropyCodec(ABC):
    """
    Entropy coding algorithm interface.

    The entropy coder consumes raw bytes and a frequency table,
    producing an encoded bitstream and the bit-length table needed
    to reconstruct the canonical decode tree.

    Implementations:
        - CanonicalHuffman (default, codec_id=0)
        - ArithmeticCoding (codec_id=1, future)
        - ANS / rANS (codec_id=2, future)
        - Vitter adaptive Huffman (codec_id=3, future)

    The codec_id is stored in the HCF header flags (bits 5-7) so the
    decoder knows which algorithm to use without external metadata.
    """

    codec_id: int  # 0-7, written to HCF header flags bits 5-7

    @abstractmethod
    def encode(self, data: bytes, freq: list[int]) -> tuple[bytes, list[int]]:
        """
        Encode raw data into a compressed bitstream.

        Args:
            data: Raw uncompressed bytes.
            freq: 256-element symbol frequency table.

        Returns:
            (bitstream_bytes, bit_lengths) where bit_lengths is a 256-element
            list (0 = symbol not present) used to reconstruct the decode tree.
        """
        ...

    @abstractmethod
    def decode(
        self,
        bitstream: "BitReader",
        bit_lengths: list[int],
        original_size: int,
    ) -> bytes:
        """
        Decode a bitstream back to original data.

        Args:
            bitstream: BitReader positioned at the start of compressed data.
            bit_lengths: 256-element bit-length table from the HCF header.
            original_size: Expected output size in bytes (from HCF header).

        Returns:
            The original uncompressed bytes.
        """
        ...
