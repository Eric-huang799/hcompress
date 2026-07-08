"""PluginMeta — standardised metadata for every hcompress plugin.

Every plugin carries a ``PluginMeta`` instance that describes its identity,
version, type, and runtime configuration (enabled/disabled, priority ordering).

The meta object is used by:
- ``PluginRegistry`` for serialisable ``get_all()`` output and enable/disable.
- ``PluginRegistry._merge_registry`` to decide which plugins are active.
- CLI ``hcompress plugin list`` and v2 Electron plugin manager UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

# Category labels that match PluginRegistry._INTERFACE_MAP categories
PLUGIN_TYPES = [
    "codec", "transform", "filter", "matchfinder", "checksum",
    "io", "block_splitter", "compress_hook", "decompress_hook",
    "observer", "extension",
]


@dataclass
class PluginMeta:
    """Standard identity and runtime-configuration blob for one plugin.

    Attributes:
        name: Human-readable plugin identifier (unique within a registry).
        version: SemVer string (e.g. ``"1.0.0"``).
        author: Plugin author / maintainer.
        description: One-line summary of what the plugin does.
        plugin_type: Category tag matching ``PluginRegistry._INTERFACE_MAP``
            values (e.g. ``"decompress_hook"``, ``"extension"``).
        priority: Execution order — lower numbers run first (default 100).
        enabled: When ``False`` the registry skips this plugin in
            ``_merge_registry`` and ``get_enabled_*`` helpers.
    """

    name: str = ""
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    plugin_type: str = ""
    priority: int = 100
    enabled: bool = True

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict (for IPC / CLI display)."""
        return asdict(self)


# ── helpers for Base class integration ───────────────────────────────────────

def default_meta(*, name: str, plugin_type: str) -> PluginMeta:
    """Convenience: create a PluginMeta with just the two required fields."""
    return PluginMeta(name=name, plugin_type=plugin_type)
