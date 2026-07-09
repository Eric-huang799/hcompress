"""LegacyMode — 老电脑兼容模式插件。

检测 CPU 核心数，≤2 核时自动跳过重计算变换（BWT/MTF），
限制并行进程数为 1，避免低配电脑卡死。

作为 IHook (compress), hook_id=1。
"""

from __future__ import annotations

import os
from typing import ClassVar

from hcompress.plugins.sdk import BaseHook
from hcompress.plugins.manifest import PluginMeta


class LegacyModePlugin(BaseHook):
    """老电脑兼容模式。

    压缩侧 on_compress_start 阶段检测 CPU 核心数，
    ≤2 核时设置 ctx._legacy_mode=True，
    引擎据此跳过重计算变换并限制并行。
    """

    hook_id: int = 1  # compress only

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="LegacyModePlugin",
        version="1.0.0",
        author="hcompress",
        description="老电脑兼容模式 — ≤2核CPU自动跳过BWT/MTF重计算，限制单核并行，防止卡死",
        plugin_type="hook",
        priority=1,
    )

    def on_compress_start(self, ctx) -> None:
        cpu_count = _detect_cpu_cores()
        if cpu_count <= 2:
            ctx._legacy_mode = True
            ctx._parallel_workers = 1
            print(f"[LegacyMode] 检测到 {cpu_count} 核 CPU，已启用兼容模式 "
                  f"(跳过 BWT/MTF，单核并行)")

    def on_compress_done(self, ctx, stats) -> None:
        if getattr(ctx, "_legacy_mode", False):
            print(f"[LegacyMode] 兼容模式压缩完成")


def _detect_cpu_cores() -> int:
    """Cross-platform CPU core count detection."""
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1
