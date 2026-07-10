"""Seven hub expanders for all pipeline interface types — chain/delegate sub-plugins via hub_config.json."""

from __future__ import annotations

import json
import os
import sys
from abc import ABC, abstractmethod
from typing import ClassVar

from hcompress.interfaces.transform import ITransform
from hcompress.interfaces.filter import IFilter
from hcompress.interfaces.codec import IEntropyCodec
from hcompress.interfaces.checksum import IChecksum
from hcompress.interfaces.io_backend import IIOBackend
from hcompress.interfaces.block_splitter import IBlockSplitter
from hcompress.interfaces.matchfinder import IMatchFinder
from hcompress.plugins.manifest import PluginMeta

CONFIG_FILE = "hub_config.json"
DEFAULT_MAX_SLOTS: dict[str, int] = {
    "transform": 5, "filter": 4, "splitter": 3, "matcher": 3,
}
SLOT_IFACE: dict[str, type] = {
    "transform": ITransform, "filter": IFilter, "codec": IEntropyCodec,
    "checksum": IChecksum, "io": IIOBackend,
    "splitter": IBlockSplitter, "matcher": IMatchFinder,
}
HUB_NAMES: dict[str, str] = {
    "transform": "TransformHub", "filter": "FilterHub",
    "codec": "CodecHub", "checksum": "ChecksumHub",
    "io": "IOHub", "splitter": "SplitterHub", "matcher": "MatcherHub",
}
HUB_DESCRIPTIONS: dict[str, str] = {
    "transform": "Transform 扩展坞 — 链式调用多个变换插件",
    "filter": "Filter 扩展坞 — 链式调用多个过滤插件",
    "codec": "Codec 扩展坞 — 选择一个编码器",
    "checksum": "Checksum 扩展坞 — 选择一个校验和算法",
    "io": "IO 扩展坞 — 选择一个 I/O 后端",
    "splitter": "Splitter 扩展坞 — 链式调用多个分块策略",
    "matcher": "Matcher 扩展坞 — 链式调用多个匹配器",
}


def _load_section(slot: str) -> list[str]:
    path = _find_config()
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {}
    section = cfg.get(slot, {})
    chain = section.get("chain", [])
    return [e["name"] for e in chain if e.get("enabled", True)]


def _save_section(slot: str, names: list[str]) -> None:
    path = _find_config()
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {}
    cfg[slot] = {"chain": [{"name": n, "enabled": True} for n in names]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _find_config() -> str:
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
    default = os.path.join(os.path.expanduser("~"), ".hcompress", CONFIG_FILE)
    os.makedirs(os.path.dirname(default), exist_ok=True)
    with open(default, "w", encoding="utf-8") as f:
        json.dump({}, f)
    return default


def _find_plugin(name: str, iface: type):
    from hcompress.plugins.registry import PluginRegistry, _INTERFACE_MAP
    dummy = PluginRegistry()
    dummy.discover_builtin()
    dummy.discover_external()
    for _iface_cls, _cat in _INTERFACE_MAP.values():
        if iface is _iface_cls:
            for inst in dummy._plugins.get(_cat, []):
                if type(inst).__name__ == name:
                    meta = getattr(type(inst), "meta", None)
                    if meta and not meta.is_hub:
                        return inst
    return None


class _HubBase(ABC):

    slot_type: ClassVar[str] = ""
    max_slots: ClassVar[int] = 1

    def __init__(self) -> None:
        self._chain: list = []
        self._names: list[str] = []
        self._reload()

    def _reload(self) -> None:
        names = _load_section(self.slot_type)
        self._chain = []
        self._names = []
        iface = SLOT_IFACE.get(self.slot_type)
        for n in names[:self.max_slots]:
            inst = _find_plugin(n, iface) if iface else None
            if inst:
                self._chain.append(inst)
                self._names.append(n)
        self.meta.sub_count = len(self._chain)

    def add(self, name: str) -> bool:
        if len(self._names) >= self.max_slots:
            return False
        iface = SLOT_IFACE.get(self.slot_type)
        inst = _find_plugin(name, iface) if iface else None
        if not inst:
            return False
        self._chain.append(inst)
        self._names.append(name)
        self.meta.sub_count = len(self._chain)
        _save_section(self.slot_type, self._names)
        return True

    def remove(self, name: str) -> bool:
        if name not in self._names:
            return False
        idx = self._names.index(name)
        self._chain.pop(idx)
        self._names.pop(idx)
        self.meta.sub_count = len(self._chain)
        _save_section(self.slot_type, self._names)
        return True

    def list_chain(self) -> list[str]:
        return list(self._names)

    @abstractmethod
    def forward(self, data): ...

    @abstractmethod
    def reverse(self, data): ...


# ── TransformHub ───────────────────────────────────────────────────

class TransformHub(ITransform, _HubBase):
    name: str = "transform_hub"
    slot_type: ClassVar[str] = "transform"
    max_slots: ClassVar[int] = DEFAULT_MAX_SLOTS["transform"]
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="TransformHub", version="1.0.0", author="hcompress",
        description=HUB_DESCRIPTIONS["transform"],
        plugin_type="transform", priority=15, is_hub=True,
    )

    def forward(self, data: bytes) -> bytes:
        for p in self._chain: data = p.forward(data)
        return data

    def reverse(self, data: bytes) -> bytes:
        for p in reversed(self._chain): data = p.reverse(data)
        return data


# ── FilterHub ──────────────────────────────────────────────────────

class FilterHub(IFilter, _HubBase):
    filter_id: int = 99
    slot_type: ClassVar[str] = "filter"
    max_slots: ClassVar[int] = DEFAULT_MAX_SLOTS["filter"]
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="FilterHub", version="1.0.0", author="hcompress",
        description=HUB_DESCRIPTIONS["filter"],
        plugin_type="filter", priority=15, is_hub=True,
    )

    def forward(self, data: bytes) -> bytes:
        for p in self._chain: data = p.apply(data)
        return data

    def reverse(self, data: bytes) -> bytes:
        for p in reversed(self._chain): data = p.revert(data)
        return data


# ── SplitterHub ────────────────────────────────────────────────────

class SplitterHub(IBlockSplitter, _HubBase):
    slot_type: ClassVar[str] = "splitter"
    max_slots: ClassVar[int] = DEFAULT_MAX_SLOTS["splitter"]
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="SplitterHub", version="1.0.0", author="hcompress",
        description=HUB_DESCRIPTIONS["splitter"],
        plugin_type="block_splitter", priority=15, is_hub=True,
    )

    def forward(self, data: bytes) -> bytes:
        return data

    def reverse(self, data: bytes) -> bytes:
        return data


# ── MatcherHub ─────────────────────────────────────────────────────

class MatcherHub(IMatchFinder, _HubBase):
    slot_type: ClassVar[str] = "matcher"
    max_slots: ClassVar[int] = DEFAULT_MAX_SLOTS["matcher"]
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="MatcherHub", version="1.0.0", author="hcompress",
        description=HUB_DESCRIPTIONS["matcher"],
        plugin_type="matchfinder", priority=15, is_hub=True,
    )

    def forward(self, data: bytes) -> bytes:
        return data

    def reverse(self, data: bytes) -> bytes:
        return data
