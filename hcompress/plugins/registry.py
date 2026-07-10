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
from hcompress.interfaces.hook import IHook
from hcompress.interfaces.observer import IObserver
from hcompress.interfaces.extension import IExtension
from hcompress.plugins.manifest import PluginMeta

# ── Interface → category mapping ────────────────────────────────────────────

_INTERFACE_MAP: dict[str, tuple[Type, str]] = {
    "IEntropyCodec":   (IEntropyCodec,   "codec"),
    "ITransform":      (ITransform,      "transform"),
    "IFilter":         (IFilter,         "filter"),
    "IMatchFinder":    (IMatchFinder,    "matchfinder"),
    "IChecksum":       (IChecksum,       "checksum"),
    "IIOBackend":      (IIOBackend,      "io"),
    "IBlockSplitter":  (IBlockSplitter,  "block_splitter"),
    "IHook":           (IHook,           "hook"),
    "IObserver":       (IObserver,       "observer"),
    "IExtension":      (IExtension,      "extension"),
}


def _infer_meta(instance: object, category: str) -> PluginMeta:
    name = type(instance).__name__
    return PluginMeta(name=name, plugin_type=category)


def _read_meta(instance: object, category: str) -> PluginMeta:
    raw = getattr(type(instance), "meta", None)
    if raw is not None:
        # If it's a ClassVar[PluginMeta] on the class, read it
        if isinstance(raw, PluginMeta):
            return raw
    # Check instance-level
    raw = getattr(instance, "meta", None)
    if isinstance(raw, PluginMeta):
        return raw
    return _infer_meta(instance, category)


# ── category name helpers ────────────────────────────────────────────────────

_CATEGORIES: list[str] = [cat for _, cat in _INTERFACE_MAP.values()]


class PluginRegistry:
    """Plugin discovery and lifecycle manager."""

    def __init__(self) -> None:
        self._plugins: dict[str, list] = {cat: [] for cat in _CATEGORIES}
        self._metas: dict[str, PluginMeta] = {}      # keyed by meta.name
        self._source_paths: dict[str, str] = {}       # meta.name → file path (for reload)
        self._loaded_paths: set[str] = set()

    # ── discovery ───────────────────────────────────────────────────────

    def discover(self, paths: list[str]) -> int:
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
        builtin_dir = os.path.join(os.path.dirname(__file__), "builtin")
        paths = [builtin_dir]

        import sys
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", "")
            if meipass:
                paths.append(os.path.join(meipass, "plugins", "builtin"))

        return self.discover(paths)

    def discover_external(self) -> int:
        import sys

        candidates = []

        # 1. Next to PyInstaller-frozen exe
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            candidates.append(os.path.join(exe_dir, "plugins"))

        # 2. User plugins directory
        candidates.append(os.path.join(os.path.expanduser("~"), ".hcompress", "plugins"))

        # 3. Current working directory
        cwd_plugins = os.path.join(os.getcwd(), "plugins")
        pkg_plugins = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
        if os.path.abspath(cwd_plugins) != os.path.abspath(pkg_plugins):
            candidates.append(cwd_plugins)

        return self.discover(candidates)

    # ── manual registration ─────────────────────────────────────────────

    def register(self, instance: object) -> bool:
        for iface_cls, category in _INTERFACE_MAP.values():
            if isinstance(instance, iface_cls):
                self._plugins[category].append(instance)
                meta = _read_meta(instance, category)
                self._metas[meta.name] = meta
                return True
        return False

    # ── enable / disable ────────────────────────────────────────────────

    def enable(self, name: str) -> bool:
        meta = self._metas.get(name)
        if meta is None:
            return False
        meta.enabled = True
        return True

    def disable(self, name: str) -> bool:
        meta = self._metas.get(name)
        if meta is None:
            return False
        meta.enabled = False
        return True

    def is_enabled(self, name: str) -> bool | None:
        meta = self._metas.get(name)
        return meta.enabled if meta else None

    def _enabled_instances(self, category: str) -> list:
        result = []
        for inst in self._plugins[category]:
            meta = self._metas.get(type(inst).__name__)
            # Also try the meta read helper for instances registered without explicit meta
            if meta is None:
                meta = _read_meta(inst, category)
            if meta is None or meta.enabled:
                result.append(inst)
        # Sort by priority (lower first)
        result.sort(key=lambda i: self._metas.get(type(i).__name__, PluginMeta()).priority)
        return result

    # ── hot reload ──────────────────────────────────────────────────────

    def reload_file(self, path: str) -> int:
        path = os.path.abspath(path)
        # Remove old instances from this file
        old_names = [
            name for name, sp in self._source_paths.items()
            if os.path.abspath(sp) == path
        ]
        for name in old_names:
            self._source_paths.pop(name, None)
            self._metas.pop(name, None)
            for cat in _CATEGORIES:
                self._plugins[cat] = [
                    inst for inst in self._plugins[cat]
                    if type(inst).__name__ not in old_names
                ]

        # Clear from loaded_paths so _load_file can run again
        self._loaded_paths.discard(path)
        # Also clear related module from sys.modules
        module_name = self._module_name(path)
        sys.modules.pop(module_name, None)

        return self._load_file(path)

    # ── filtered getters (ALL instances, for backward compat) ───────────

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
        return [i for i in self._plugins["hook"] if getattr(i, "hook_id", 0) in (0, 1)]

    def get_decompress_hooks(self) -> list:
        return [i for i in self._plugins["hook"] if getattr(i, "hook_id", 0) in (0, 2)]

    def get_observers(self) -> list:
        return list(self._plugins["observer"])

    def get_extensions(self) -> list:
        return list(self._plugins["extension"])

    # ── filtered getters (ENABLED only, for engine) ────────────────────

    def get_enabled_codecs(self) -> list:
        return self._enabled_instances("codec")

    def get_enabled_transforms(self) -> list:
        return self._enabled_instances("transform")

    def get_enabled_filters(self) -> list:
        return self._enabled_instances("filter")

    def get_enabled_matchfinders(self) -> list:
        return self._enabled_instances("matchfinder")

    def get_enabled_checksums(self) -> list:
        return self._enabled_instances("checksum")

    def get_enabled_io_backends(self) -> list:
        return self._enabled_instances("io")

    def get_enabled_block_splitters(self) -> list:
        return self._enabled_instances("block_splitter")

    def get_enabled_compress_hooks(self) -> list:
        return [i for i in self._enabled_instances("hook") if getattr(i, "hook_id", 0) in (0, 1)]

    def get_enabled_decompress_hooks(self) -> list:
        return [i for i in self._enabled_instances("hook") if getattr(i, "hook_id", 0) in (0, 2)]

    def get_enabled_observers(self) -> list:
        return self._enabled_instances("observer")

    def get_enabled_extensions(self) -> list:
        return self._enabled_instances("extension")

    # ── serializable snapshot ───────────────────────────────────────────

    def get_all(self) -> dict:
        plugins: list[dict] = []
        for category in _CATEGORIES:
            for inst in self._plugins[category]:
                meta = _read_meta(inst, category)
                # Ensure meta is tracked
                if meta.name not in self._metas:
                    self._metas[meta.name] = meta
                plugins.append(meta.to_dict())

        enabled_count = sum(1 for p in plugins if p["enabled"])
        return {
            "plugins": plugins,
            "count": len(plugins),
            "count_enabled": enabled_count,
        }

    def get_meta(self, name: str) -> PluginMeta | None:
        return self._metas.get(name)

    def get_all_metas(self) -> dict[str, PluginMeta]:
        # Reconcile: ensure every loaded instance has a tracked meta
        for category in _CATEGORIES:
            for inst in self._plugins[category]:
                meta = _read_meta(inst, category)
                if meta.name not in self._metas:
                    self._metas[meta.name] = meta
        return dict(self._metas)

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
            count = self._scan_module(module, source_path=path)
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
            count += self._scan_module(module, source_path=path)
            self._loaded_paths.add(init)
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

    def _scan_module(self, module, *, source_path: str = "") -> int:
        count = 0
        for name in dir(module):
            obj = getattr(module, name)
            if not isinstance(obj, type):
                continue
            if obj.__module__ != module.__name__:
                continue
            for iface_cls, category in _INTERFACE_MAP.values():
                try:
                    if issubclass(obj, iface_cls) and obj is not iface_cls:
                        try:
                            instance = obj()
                        except Exception:
                            continue
                        self._plugins[category].append(instance)
                        meta = _read_meta(instance, category)
                        self._metas[meta.name] = meta
                        if source_path:
                            self._source_paths[meta.name] = source_path
                        count += 1
                except TypeError:
                    pass
        return count

    @staticmethod
    def _module_name(path: str) -> str:
        name = os.path.splitext(os.path.basename(path))[0]
        return f"hcompress_plugin_{name}"
