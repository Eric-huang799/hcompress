"""IIOBackend / IIOBitStream — I/O abstraction interfaces."""

from abc import ABC, abstractmethod
from typing import BinaryIO


class IIOBackend(ABC):
    """
    Input / output backend abstraction.

    The default FileIO backend reads from / writes to the local filesystem.
    Alternative backends enable in-memory processing, streaming over a
    network socket, memory-mapped I/O for very large files, or custom
    virtual filesystems (e.g. S3, inside a .tar, etc.).

    Implementations:
        - FileIO    (default) — open() / read() / write()
        - MemoryIO  — BytesIO buffers, useful for testing or embedding
        - StreamIO  — stdin/stdout or socket streams
        - MMapIO    — mmap for zero-copy large-file access
    """

    @abstractmethod
    def open_read(self, path: str) -> BinaryIO:
        """Open a source for reading bytes."""
        ...

    @abstractmethod
    def open_write(self, path: str) -> BinaryIO:
        """Open a destination for writing bytes."""
        ...

    @abstractmethod
    def source_size(self, source: str | BinaryIO) -> int:
        """Return total size in bytes of the source (or -1 if unknown)."""
        ...


class IIOBitStream(ABC):
    """
    Bit-level I/O stream, layered on top of a byte-level IIOBackend.

    This is the low-level interface that the entropy coder interacts with.
    The default Python implementation (BitWriter / BitReader in bitstream.py)
    fulfills this contract; the C-accelerated version in c_ext/ uses the
    same interface.
    """

    @abstractmethod
    def read_bits(self, n: int) -> int:
        """Read n bits (1-32) from the stream. Returns a uint32."""
        ...

    @abstractmethod
    def write_bits(self, value: int, n: int) -> None:
        """Write the lower n bits of value to the stream."""
        ...

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered bits to the underlying byte stream."""
        ...
