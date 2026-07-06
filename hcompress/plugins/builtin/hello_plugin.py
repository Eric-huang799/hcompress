"""HelloPlugin — 测试插件，验证自动加载功能。"""
from hcompress.plugins.sdk import BaseDecompressHook

class HelloPlugin(BaseDecompressHook):
    """每次解压完打个招呼，证明插件系统正常工作。"""

    def on_start(self, ctx):
        print(f"[HelloPlugin] 开始解压: {ctx.input_path}")

    def on_done(self, ctx, stats):
        print(f"[HelloPlugin] 解压完成! {stats.original_size} 字节")
