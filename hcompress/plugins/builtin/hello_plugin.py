"""HelloPlugin — 测试插件，验证自动加载功能。"""
from typing import ClassVar

from hcompress.plugins.sdk import BaseDecompressHook
from hcompress.plugins.manifest import PluginMeta


class HelloPlugin(BaseDecompressHook):
    """每次解压完打个招呼，证明插件系统正常工作。"""

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="HelloPlugin",
        version="1.0.0",
        author="hcompress team",
        description="测试插件 —— 解压时打印问候信息，验证自动加载",
        plugin_type="decompress_hook",
        priority=999,
    )

    def on_start(self, ctx):
        print(f"[HelloPlugin] 开始解压: {ctx.input_path}")

    def on_done(self, ctx, stats):
        print(f"[HelloPlugin] 解压完成! {stats.original_size} 字节")
