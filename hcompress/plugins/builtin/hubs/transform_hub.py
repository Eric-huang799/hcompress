"""TransformHub — ITransform 扩展坞。

占用 1 个 transform 槽位，肚里承载 N 个普通变换插件。
配置文件: plugins/transform_hub.json
"""

from __future__ import annotations

import json
import os
import sys
from typing import ClassVar

from hcompress.interfaces.transform import ITransform
from hcompress.plugins.manifest import PluginMeta

CONFIG_FILE = "transform_hub.json"
DEFAULT_CONFIG = {"chain": []}


def _find_config() -> str:
    """Search for config next to exe, in user dir, and cwd."""
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "plugins", CONFIG_FILE))
        candidates.append(os.path.join(exe_dir, CONFIG_FILE))
    candidates.append(os.path.join(os.path.expanduser("~"), ".hcompress", CONFIG_FILE))
    candidates.append(os.path.join(os.getcwd(), CONFIG_FILE))
    for p in candidates:
        if os.path.isfile(p):
            return p
    # Return default write location
    default = os.path.join(os.path.expanduser("~"), ".hcompress", CONFIG_FILE)
    os.makedirs(os.path.dirname(default), exist_ok=True)
    with open(default, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f)
    return default


class TransformHub(ITransform):
    """Transform 扩展坞。

    Config JSON:
        {"chain": [{"name": "MTFTransform", "enabled": true}, ...]}

    子插件按顺序链式调用 forward()，逆向时 reversed 调用 reverse()。
    """

    name: str = "transform_hub"
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="TransformHub",
        version="1.0.0",
        author="hcompress",
        description="Transform扩展坞 — 1个插口承载多个普通变换插件，链式调用",
        plugin_type="transform",
        priority=15,
        is_hub=True,
    )

    def __init__(self) -> None:
        self._chain: list[ITransform] = []
        self._names: list[str] = []
        self._config_path = _find_config()
        self.reload()

    def reload(self) -> None:
        """Reload chain from config JSON."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            cfg = DEFAULT_CONFIG

        chain = cfg.get("chain", [])
        self._chain = []
        self._names = []
        for entry in chain:
            if not entry.get("enabled", True):
                continue
            name = entry.get("name", "")
            # Try to find class by name in builtin transforms
            instance = self._find_plugin(name)
            if instance:
                self._chain.append(instance)
                self._names.append(name)

        self.meta.sub_count = len(self._chain)

    def _find_plugin(self, name: str) -> ITransform | None:
        """Find a transform plugin by class name."""
        # Search registered transforms in the global registry
        from hcompress.plugins.registry import PluginRegistry
        dummy = PluginRegistry()
        dummy.discover_builtin()
        dummy.discover_external()
        for t in dummy.get_transforms():
            if type(t).__name__ == name and not isinstance(t, TransformHub):
                return t
        return None

    def _save(self) -> None:
        """Write current chain back to config."""
        cfg = {"chain": [
            {"name": n, "enabled": True} for n in self._names
        ]}
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    def add(self, name: str) -> bool:
        """Add a plugin to the chain."""
        inst = self._find_plugin(name)
        if not inst:
            return False
        self._chain.append(inst)
        self._names.append(name)
        self.meta.sub_count = len(self._chain)
        self._save()
        return True

    def remove(self, name: str) -> bool:
        """Remove a plugin from the chain."""
        if name not in self._names:
            return False
        idx = self._names.index(name)
        self._chain.pop(idx)
        self._names.pop(idx)
        self.meta.sub_count = len(self._chain)
        self._save()
        return True

    def reorder(self, names: list[str]) -> bool:
        """Reorder the chain."""
        if set(names) != set(self._names):
            return False
        new_chain = []
        for n in names:
            idx = self._names.index(n)
            new_chain.append(self._chain[idx])
        self._chain = new_chain
        self._names = list(names)
        self._save()
        return True

    def list_chain(self) -> list[str]:
        """Return ordered list of plugin names in the chain."""
        return list(self._names)

    # ── ITransform ─────────────────────────────────────────────────────

    def forward(self, data: bytes) -> bytes:
        for p in self._chain:
            data = p.forward(data)
        return data

    def reverse(self, data: bytes) -> bytes:
        for p in reversed(self._chain):
            data = p.reverse(data)
        return data
