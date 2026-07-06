"""Plugin scaffolding — generate a ready-to-edit plugin skeleton."""

from __future__ import annotations

import os

# ── Templates ───────────────────────────────────────────────────────────────

_HEADER = '''"""{} — {}. """
'''

_TEMPLATES: dict[str, str] = {
    "decompress-hook": _HEADER + '''
from hcompress.plugins.sdk import BaseDecompressHook


class {class_name}(BaseDecompressHook):
    """TODO: describe what this hook does."""

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
from hcompress.plugins.sdk import BaseCompressHook


class {class_name}(BaseCompressHook):
    """TODO: describe what this hook does."""

    def on_done(self, ctx, stats):
        # Example: log compression stats
        # print(f"Compressed {{stats.original_size}} → {{stats.compressed_size}} "
        #       f"in {{stats.elapsed_ms:.0f}} ms")
        pass
''',

    "extension": _HEADER + '''
from hcompress.plugins.sdk import BaseExtension


class {class_name}(BaseExtension):
    """TODO: describe what this extension does."""

    extension_id = "{ext_id}"
    version = "0.1.0"

    def on_compress_data(self, ctx, data, stage):
        # stage is one of: 'raw', 'post_freq', 'post_encode', 'pre_write'
        return data

    def on_decompress_data(self, ctx, data, stage):
        # stage is one of: 'raw_header', 'post_decode', 'pre_write'
        return data

    def get_extension_data(self):
        # Return dict to persist into HCF header
        return {{}}

    def set_extension_data(self, data):
        # Restore dict from HCF header
        pass
''',

    "checksum": _HEADER + '''
from hcompress.plugins.sdk import BaseChecksum


class {class_name}(BaseChecksum):
    """TODO: describe this checksum algorithm."""

    checksum_id = 255  # pick an unused id
    digest_size = 4     # bytes

    def compute(self, data):
        # TODO: implement checksum
        import hashlib
        return hashlib.sha256(data).digest()[:self.digest_size]
''',

    "transform": _HEADER + '''
from hcompress.plugins.sdk import BaseTransform


class {class_name}(BaseTransform):
    """TODO: describe this transform (e.g. BWT, MTF, RLE)."""

    name = "{ext_id}"

    def forward(self, data):
        # Transform before encoding
        return data

    def reverse(self, data):
        # Reverse after decoding
        return data
''',
}

_DESCRIPTIONS = {
    "decompress-hook": "Decompression lifecycle hook (bomb guard, logging, …)",
    "compress-hook": "Compression lifecycle hook (logging, metrics, …)",
    "extension": "Universal extension (encryption, signing, metadata, …)",
    "checksum": "Custom checksum algorithm",
    "transform": "Reversible data transform (BWT, RLE, …)",
}


def scaffold(name: str, plugin_type: str, output_dir: str = ".") -> str:
    """Generate a plugin skeleton file.

    Args:
        name: Plugin name (kebab-case, e.g. "my-bomb-guard").
        plugin_type: One of: decompress-hook, compress-hook, extension,
                     checksum, transform.
        output_dir: Directory to write the file to.

    Returns:
        The path to the generated file.
    """
    if plugin_type not in _TEMPLATES:
        available = ", ".join(_TEMPLATES)
        raise ValueError(
            f"Unknown plugin type '{plugin_type}'. Available: {available}"
        )

    # Derive class name
    parts = name.replace("-", " ").replace("_", " ").split()
    class_name = "".join(p.capitalize() for p in parts)

    # Derive extension id
    ext_id = f"com.example.{name}"

    # Derive file name
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
