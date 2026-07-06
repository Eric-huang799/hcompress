"""IBlockSplitter — large-file block partitioning interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Block:
    """A contiguous chunk of file data with its offset."""

    offset: int      # byte offset in the original file
    data: bytes      # raw data for this block
    index: int       # 0-based block index


class IBlockSplitter(ABC):
    """
    Block partitioning strategy.

    Splitting large files into independent blocks enables:
        - Parallel compression / decompression (one thread per block).
        - Streaming: start encoding block 1 while block 0 is still writing.
        - Memory-efficiency: only one block in RAM at a time.

    The default strategy is a single block (whole file at once).

    Implementations:
        - FixedSize(N)     — split every N MiB.
        - ContentBased     — split at content-defined boundaries (CDC, like zpaq).
        - Adaptive         — vary block size based on local entropy.
    """

    @abstractmethod
    def split(self, data: bytes) -> list[Block]:
        """
        Partition data into blocks. Each block is compressed independently
        and will have its own mini-header within the HCF bitstream.
        """
        ...

    @abstractmethod
    def merge(self, blocks: list[Block]) -> bytes:
        """Reassemble blocks in index order (used after decoding all blocks)."""
        ...
