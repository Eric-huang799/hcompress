"""多线程并行压缩插件 — 大文件自动启用多进程并行。"""
from typing import ClassVar

from hcompress.plugins.sdk import BaseHook
from hcompress.plugins.manifest import PluginMeta

PARALLEL_THRESHOLD = 50 * 1024 * 1024  # 50 MB, avoids PyInstaller freeze support issues
WORKERS = 4


class ParallelCompressPlugin(BaseHook):
    hook_id: int = 1  # compress only

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="ParallelCompressPlugin", version="1.0.0", author="hcompress team",
        description="大文件(>256KB)自动启用 ProcessPoolExecutor 多进程并行",
        plugin_type="hook", priority=90,
    )

    supports_parallel: bool = True

    def on_compress_start(self, ctx):
        if ctx.original_size > PARALLEL_THRESHOLD:
            ctx._parallel_workers = WORKERS
            ctx._parallel_enabled = True
        else:
            ctx._parallel_enabled = False

    def on_compress_done(self, ctx, stats):
        if getattr(ctx, "_parallel_enabled", False):
            print(f"[ParallelCompress] 多进程并行完成: {ctx._parallel_workers} workers")
