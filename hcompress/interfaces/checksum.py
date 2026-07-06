"""IChecksum — pluggable integrity verification interface."""

from abc import ABC, abstractmethod


class IChecksum(ABC):
    """
    Integrity checksum interface.

    The checksum of the *original* data is computed during compression
    and verified against the decoded data during decompression.

    Implementations:
        - CRC32  (default, checksum_id=0, 4-byte digest, hardware-accelerable)
        - xxHash (checksum_id=1, 8-byte digest, very fast on CPU)
        - BLAKE3 (checksum_id=2, 32-byte digest, cryptographic + fast)
        - SHA-256 (checksum_id=3, 32-byte digest, cryptographic, FIPS)
    """

    checksum_id: int
    digest_size: int  # output size in bytes

    @abstractmethod
    def compute(self, data: bytes) -> bytes:
        """Compute checksum of raw data. Must return exactly digest_size bytes."""
        ...

    @abstractmethod
    def verify(self, data: bytes, expected: bytes) -> bool:
        """Return True if data's checksum matches expected."""
        ...
