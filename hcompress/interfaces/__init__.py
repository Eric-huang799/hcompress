"""hcompress interfaces — abstract contracts for extensibility.

All interfaces are pure ABCs with no implementation.
Import them directly for building custom extensions:

    from hcompress.interfaces import IEntropyCodec, ITransform, IExtension
"""

from hcompress.interfaces.codec import IEntropyCodec
from hcompress.interfaces.transform import ITransform
from hcompress.interfaces.filter import IFilter
from hcompress.interfaces.matchfinder import IMatchFinder, Match
from hcompress.interfaces.checksum import IChecksum
from hcompress.interfaces.io_backend import IIOBackend, IIOBitStream
from hcompress.interfaces.block_splitter import IBlockSplitter, Block
from hcompress.interfaces.hook import ICompressHook, IDecompressHook, CompressContext, DecompressContext
from hcompress.interfaces.observer import IObserver, CompressEvent
from hcompress.interfaces.extension import IExtension

__all__ = [
    "IEntropyCodec",
    "ITransform",
    "IFilter",
    "IMatchFinder",
    "Match",
    "IChecksum",
    "IIOBackend",
    "IIOBitStream",
    "IBlockSplitter",
    "Block",
    "ICompressHook",
    "IDecompressHook",
    "CompressContext",
    "DecompressContext",
    "IObserver",
    "CompressEvent",
    "IExtension",
]
