"""HelloPlugin — 测试插件，验证自动加载功能。"""
from typing import ClassVar

from hcompress.plugins.sdk import BaseHook
from hcompress.plugins.manifest import PluginMeta


class HelloPlugin(BaseHook):
    hook_id: int = 2  # decompress only

    meta: ClassVar[PluginMeta] = PluginMeta(
        name="HelloPlugin", version="1.0.0", author="hcompress team",
        description="测试插件 —— 解压时打印问候信息，验证自动加载",
        plugin_type="hook", priority=999,
    )

    def on_decompress_start(self, ctx):
        print(f"[HelloPlugin] 开始解压: {ctx.input_path}")

    def on_decompress_done(self, ctx, stats):
        print(f"[HelloPlugin] 解压完成! {stats.original_size} 字节")
