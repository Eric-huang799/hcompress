"""PluginRegistry — discover, load, and manage hcompress plugins."""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Type

from hcompress.interfaces.codec import IEntropyCodec
from hcompress.interfaces.transform import ITransform
from hcompress.interfaces.filter import IFilter
from hcompress.interfaces.matchfinder import IMatchFinder
from hcompress.interfaces.checksum import IChecksum
from hcompress.interfaces.io_backend import IIOBackend
from hcompress.interfaces.block_splitter import IBlockSplitter
from hcompress.interfaces.hook import ICompressHook, IDecompressHook
from hcompress.interfaces.observer import IObserver
from hcompress.interfaces.extension import IExtension

# ── Interface → category mapping ────────────────────────────────────────────

_INTERFACE_MAP: dict[str, tuple[Type, str]] = {
    "IEntropyCodec":   (IEntropyCodec,   "codec"),
    "ITransform":      (ITransform,      "transform"),
    "IFilter":         (IFilter,         "filter"),
    "IMatchFinder":    (IMatchFinder,    "matchfinder"),
    "IChecksum":       (IChecksum,       "checksum"),
    "IIOBackend":      (IIOBackend,      "io"),
    "IBlockSplitter":  (IBlockSplitter,  "block_splitter"),
    "ICompressHook":   (ICompressHook,   "compress_hook"),
    "IDecompressHook": (IDecompressHook, "decompress_hook"),
    "IObserver":       (IObserver,       "observer"),
    "IExtension":      (IExtension,      "extension"),
}


class PluginRegistry:
    """Plugin discovery and lifecycle manager.

    Usage::

        registry = PluginRegistry()
        registry.discover(["~/.hcompress/plugins", "./plugins"])
        registry.discover_builtin()   # load bomb_guard etc.

        config = CompressConfig()
        config.hooks = registry.get_compress_hooks()
        config.extensions = registry.get_extensions()
    """

    def __init__(self) -> None:
        self._plugins: dict[str, list] = {cat: [] for _, cat in _INTERFACE_MAP.values()}
        self._loaded_paths: set[str] = set()

    # ── discovery ───────────────────────────────────────────────────────

    def discover(self, paths: list[str]) -> int:
        """Scan *paths* for plugin ``.py`` files, import them, register plugins.

        Returns the number of newly loaded plugins.
        """
        count = 0
        for base in paths:
            base = os.path.expanduser(base)
            if not os.path.isdir(base):
                continue
            for entry in sorted(os.listdir(base)):
                if entry.startswith("_") or entry.startswith("."):
                    continue
                full = os.path.join(base, entry)
                if os.path.isfile(full) and entry.endswith(".py"):
                    count += self._load_file(full)
                elif os.path.isdir(full) and os.path.isfile(os.path.join(full, "__init__.py")):
                    count += self._load_package(full)
        return count

    def discover_builtin(self) -> int:
        """Load built-in plugins shipped with hcompress.

        Handles both normal installs and PyInstaller-frozen bundles.
        """
        # Normal Python path
        builtin_dir = os.path.join(os.path.dirname(__file__), "builtin")
        paths = [builtin_dir]

        # PyInstaller bundle: data files extracted to sys._MEIPASS
        import sys
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", "")
            if meipass:
                paths.append(os.path.join(meipass, "plugins", "builtin"))

        return self.discover(paths)

    # ── manual registration ─────────────────────────────────────────────

    def register(self, instance: object) -> bool:
        """Manually register a plugin instance.

        Returns True if the instance matched a known interface.
        """
        for iface_cls, category in _INTERFACE_MAP.values():
            if isinstance(instance, iface_cls):
                self._plugins[category].append(instance)
                return True
        return False

    # ── filtered getters ────────────────────────────────────────────────

    def get_codecs(self) -> list:
        return list(self._plugins["codec"])

    def get_transforms(self) -> list:
        return list(self._plugins["transform"])

    def get_filters(self) -> list:
        return list(self._plugins["filter"])

    def get_matchfinders(self) -> list:
        return list(self._plugins["matchfinder"])

    def get_checksums(self) -> list:
        return list(self._plugins["checksum"])

    def get_io_backends(self) -> list:
        return list(self._plugins["io"])

    def get_block_splitters(self) -> list:
        return list(self._plugins["block_splitter"])

    def get_compress_hooks(self) -> list:
        return list(self._plugins["compress_hook"])

    def get_decompress_hooks(self) -> list:
        return list(self._plugins["decompress_hook"])

    def get_observers(self) -> list:
        return list(self._plugins["observer"])

    def get_extensions(self) -> list:
        return list(self._plugins["extension"])

    def get_all(self) -> dict[str, list]:
        """Return all registered plugins keyed by category."""
        return {cat: list(lst) for cat, lst in self._plugins.items()}

    # ── internal ────────────────────────────────────────────────────────

    def _load_file(self, path: str) -> int:
        if path in self._loaded_paths:
            return 0
        count = 0
        module_name = self._module_name(path)
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                return 0
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            count = self._scan_module(module)
            self._loaded_paths.add(path)
        except Exception:
            import traceback
            traceback.print_exc()
        return count

    def _load_package(self, path: str) -> int:
        init = os.path.join(path, "__init__.py")
        if init in self._loaded_paths:
            return 0
        count = 0
        package_name = os.path.basename(path)
        try:
            spec = importlib.util.spec_from_file_location(
                package_name, init,
                submodule_search_locations=[path],
            )
            if spec is None or spec.loader is None:
                return 0
            module = importlib.util.module_from_spec(spec)
            sys.modules[package_name] = module
            spec.loader.exec_module(module)
            count += self._scan_module(module)
            self._loaded_paths.add(init)
            # Also scan sibling .py files in the package
            for entry in sorted(os.listdir(path)):
                if entry.startswith("_") or not entry.endswith(".py"):
                    continue
                full = os.path.join(path, entry)
                if full == init:
                    continue
                count += self._load_file(full)
        except Exception:
            import traceback
            traceback.print_exc()
        return count

    def _scan_module(self, module) -> int:
        """Instantiate and register plugin classes found in *module*."""
        count = 0
        for name in dir(module):
            obj = getattr(module, name)
            if not isinstance(obj, type):
                continue
            if obj.__module__ != module.__name__:
                continue  # imported, not defined here
            for iface_cls, category in _INTERFACE_MAP.values():
                try:
                    if issubclass(obj, iface_cls) and obj is not iface_cls:
                        try:
                            instance = obj()
                            self._plugins[category].append(instance)
                            count += 1
                        except Exception:
                            pass  # can't instantiate (e.g. missing params)
                except TypeError:
                    pass  # obj is not a class
        return count

    @staticmethod
    def _module_name(path: str) -> str:
        """Derive a unique module name from a file path."""
        name = os.path.splitext(os.path.basename(path))[0]
        return f"hcompress_plugin_{name}"
