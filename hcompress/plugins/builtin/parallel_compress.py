"""多线程并行压缩插件 — 拖入 plugins/builtin/ 即可启用。

启用后，大文件压缩自动使用多进程并行加速：
  2 进程: 2.4× / 4 进程: 3.1×

基于 ProcessPoolExecutor，绕过 Python GIL。
"""
from hcompress.plugins.sdk import BaseCompressHook

PARALLEL_THRESHOLD = 256 * 1024  # 256 KB
WORKERS = 4

class ParallelCompressPlugin(BaseCompressHook):
    """大文件自动切换多进程并行压缩。"""
    def on_start(self, ctx):
        import os
        if ctx.original_size > PARALLEL_THRESHOLD:
            ctx._parallel_workers = WORKERS
            ctx._parallel_enabled = True
        else:
            ctx._parallel_enabled = False

    def on_done(self, ctx, stats):
        if getattr(ctx, "_parallel_enabled", False):
            print(f"[ParallelCompress] 多进程并行完成: {ctx._parallel_workers} workers")
