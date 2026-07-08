"""Plugin scaffolding — generate a ready-to-edit plugin skeleton.

Supports all 10 plugin types with metadata included.
"""

from __future__ import annotations

import os

# ── Templates ───────────────────────────────────────────────────────────────

_HEADER = '''"""{} — {}. """
'''

_TEMPLATES: dict[str, str] = {
    "decompress-hook": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseDecompressHook
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseDecompressHook):
    """TODO: describe what this hook does."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="decompress_hook",
    )

    def on_header_read(self, ctx, header):
        # Example: bomb detection
        # ratio = header.original_size / ctx.compressed_size
        # if ratio > 100:
        #     raise RuntimeError("Suspicious expansion ratio!")
        return True  # True = continue, False = abort

    # Other hooks available (override as needed):
    #   on_start(ctx)
    #   on_block_decoded(ctx, block_idx, encoded, raw)
    #   on_done(ctx, stats)
    #   on_error(ctx, error)
''',

    "compress-hook": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseCompressHook
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseCompressHook):
    """TODO: describe what this hook does."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="compress_hook",
    )

    def on_done(self, ctx, stats):
        # Example: log compression stats
        pass

    # Other hooks: on_start, on_freq_done, on_header_written,
    #              on_block_encoded, on_error
''',

    "extension": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseExtension
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseExtension):
    """TODO: describe what this extension does."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="extension",
    )

    extension_id = "{ext_id}"

    def on_compress_data(self, ctx, data, stage):
        # stage is one of: 'raw', 'post_freq', 'post_encode', 'pre_write'
        return data

    def on_decompress_data(self, ctx, data, stage):
        # stage is one of: 'raw_header', 'post_decode', 'pre_write'
        return data

    def get_extension_data(self):
        return {{}}

    def set_extension_data(self, data):
        pass
''',

    "checksum": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseChecksum
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseChecksum):
    """TODO: describe this checksum algorithm."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="checksum",
    )

    checksum_id = 255
    digest_size = 4

    def compute(self, data):
        import hashlib
        return hashlib.sha256(data).digest()[:self.digest_size]
''',

    "transform": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseTransform
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseTransform):
    """TODO: describe this transform (e.g. BWT, MTF, RLE)."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="transform",
    )

    name = "{ext_id}"

    def forward(self, data):
        return data

    def reverse(self, data):
        return data
''',

    "codec": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseCodec
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseCodec):
    """TODO: describe this entropy codec (e.g. ANS, Arithmetic)."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="codec",
    )

    codec_id = 7

    def encode(self, data, freq):
        raise NotImplementedError

    def decode(self, bitstream, bit_lengths, original_size):
        raise NotImplementedError
''',

    "filter": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseFilter
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseFilter):
    """TODO: describe this filter (e.g. delta, PNG predictor)."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="filter",
    )

    filter_id = 0

    def apply(self, data):
        return data

    def revert(self, data):
        return data
''',

    "matchfinder": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseMatchFinder
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseMatchFinder):
    """TODO: describe this match finder (e.g. HashChain, BinaryTree)."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="matchfinder",
    )

    @property
    def window_size(self):
        return 32768

    def find_matches(self, data, pos):
        return []
''',

    "io-backend": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseIOBackend
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseIOBackend):
    """TODO: describe this IO backend (e.g. S3, mmap)."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="io",
    )

    def open_read(self, path):
        raise NotImplementedError

    def open_write(self, path):
        raise NotImplementedError

    def source_size(self, source):
        raise NotImplementedError
''',

    "block-splitter": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseBlockSplitter
from hcompress.plugins.manifest import PluginMeta
from hcompress.interfaces.block_splitter import Block


class {class_name}(BaseBlockSplitter):
    """TODO: describe this splitter (e.g. fixed-size, content-defined)."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="block_splitter",
    )

    def split(self, data):
        return [Block(offset=0, data=data, index=0)]

    def merge(self, blocks):
        blocks.sort(key=lambda b: b.index)
        return b"".join(b.data for b in blocks)
''',

    "observer": _HEADER + '''
from typing import ClassVar

from hcompress.plugins.sdk import BaseObserver
from hcompress.plugins.manifest import PluginMeta


class {class_name}(BaseObserver):
    """TODO: describe this observer (e.g. progress logger, audit trail)."""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="{class_name}",
        version="0.1.0",
        author="",
        description="TODO",
        plugin_type="observer",
    )

    def on_progress(self, current, total, phase):
        pass

    def on_event(self, event):
        pass
''',
}

_DESCRIPTIONS: dict[str, str] = {
    "decompress-hook": "Decompression lifecycle hook (bomb guard, logging, …)",
    "compress-hook": "Compression lifecycle hook (logging, metrics, …)",
    "extension": "Universal extension (encryption, signing, metadata, …)",
    "checksum": "Custom checksum algorithm",
    "transform": "Reversible data transform (BWT, RLE, …)",
    "codec": "Custom entropy codec (ANS, Arithmetic, …)",
    "filter": "Pre-processing filter (delta, PNG predictor, …)",
    "matchfinder": "LZ-style dictionary match finder",
    "io-backend": "Custom I/O backend (S3, mmap, socket, …)",
    "block-splitter": "Block partitioning strategy (fixed, CDC, …)",
    "observer": "Progress/event observer (logger, audit, …)",
}


def scaffold(name: str, plugin_type: str, output_dir: str = ".") -> str:
    """Generate a plugin skeleton file.

    Args:
        name: Plugin name (kebab-case, e.g. ``"my-bomb-guard"``).
        plugin_type: One of: ``decompress-hook``, ``compress-hook``,
            ``extension``, ``checksum``, ``transform``, ``codec``,
            ``filter``, ``matchfinder``, ``io-backend``,
            ``block-splitter``, ``observer``.
        output_dir: Directory to write the file to.

    Returns:
        The path to the generated file.
    """
    if plugin_type not in _TEMPLATES:
        available = ", ".join(sorted(_TEMPLATES))
        raise ValueError(
            f"Unknown plugin type '{plugin_type}'. Available: {available}"
        )

    parts = name.replace("-", " ").replace("_", " ").split()
    class_name = "".join(p.capitalize() for p in parts)

    ext_id = f"com.example.{name}"

    filename = name.replace(" ", "_").replace("-", "_") + ".py"
    if not filename.endswith(".py"):
        filename += ".py"

    template = _TEMPLATES[plugin_type]
    desc = _DESCRIPTIONS.get(plugin_type, plugin_type)
    content = template.format(
        name, desc, class_name=class_name, ext_id=ext_id,
    ).lstrip()

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath
