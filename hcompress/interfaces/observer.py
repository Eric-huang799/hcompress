"""IObserver — progress / event / log observer interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto


class EventType(Enum):
    """Granular pipeline events for observer callbacks."""

    # Compress events
    COMPRESS_FILE_OPENED = auto()
    COMPRESS_FREQ_START = auto()
    COMPRESS_FREQ_DONE = auto()
    COMPRESS_HEADER_WRITTEN = auto()
    COMPRESS_BLOCK_START = auto()
    COMPRESS_BLOCK_DONE = auto()
    COMPRESS_CHECKSUM_DONE = auto()
    COMPRESS_DONE = auto()
    COMPRESS_ERROR = auto()

    # Decompress events
    DECOMPRESS_FILE_OPENED = auto()
    DECOMPRESS_HEADER_READ = auto()
    DECOMPRESS_BLOCK_START = auto()
    DECOMPRESS_BLOCK_DONE = auto()
    DECOMPRESS_CHECKSUM_VERIFIED = auto()
    DECOMPRESS_DONE = auto()
    DECOMPRESS_ERROR = auto()


@dataclass
class CompressEvent:
    """A lightweight event emitted during compression / decompression."""

    type: EventType
    message: str = ""
    elapsed_ms: float = 0.0
    bytes_processed: int = 0
    bytes_total: int = 0


class IObserver(ABC):
    """
    Observer interface — progress, events, and log callbacks.

    Observers receive read-only events; they MUST NOT mutate pipeline state.
    Multiple observers can be registered simultaneously (e.g. RichProgress
    for the terminal + FileLogger for audit trail).

    Implementations:
        - RichProgress  — animated progress bars via the `rich` library.
        - FileLogger    — append structured logs to a file.
        - NullObserver  — no-op (default when no observer is configured).
    """

    @abstractmethod
    def on_progress(self, current: int, total: int, phase: str) -> None:
        """
        Called periodically during long-running operations.

        Args:
            current: bytes / blocks processed so far.
            total:   total bytes / blocks expected.
            phase:   human-readable phase label ("encoding", "decoding", …).
        """
        ...

    @abstractmethod
    def on_event(self, event: CompressEvent) -> None:
        """Called at discrete pipeline milestones."""
        ...
