"""hcompress TUI — Textual-powered terminal interface with file browser."""

from __future__ import annotations

import os
import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button, DirectoryTree, Footer, Header, Label,
    ProgressBar, Static, Switch
)

from hcompress.engine import compress, compress_parallel, CompressConfig, DecompressConfig
from hcompress.plugins import PluginRegistry


class HcompressTUI(App[None]):
    """hcompress terminal UI with file browser."""

    CSS = """
    Screen { background: #0d0d14; }
    Header { background: #16162a; color: #6c8cff; }
    Footer { background: #16162a; }

    #sidebar {
        width: 38; background: #111122; border-right: solid #2a2a4a;
        padding: 1;
    }
    #sidebar Label { padding: 1 2; color: #888; text-style: bold; }
    DirectoryTree { height: 1fr; background: #111122; border: solid #2a2a4a; }

    #main { padding: 1 2; }
    #info { height: 5; background: #16162a; padding: 1 2; margin-bottom: 1; }
    #info Label { padding: 0 1; }
    #info .path { color: #6c8cff; text-style: bold; }
    #info .size { color: #e5b83c; }
    #info .ratio { color: #3ec97e; text-style: bold; }
    #progress { height: 3; margin-top: 1; background: #16162a; padding: 0 2; }
    #actions { height: 4; margin-top: 1; }
    #actions Horizontal { height: 1fr; }
    Button { margin: 0 1; }
    Button.primary { background: #6c8cff; color: #fff; }
    Button.success { background: #3ec97e; color: #0d0d14; }
    Button.warning { background: #e5b83c; color: #0d0d14; }
    Button.danger { background: #e5535b; color: #fff; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", show=True),
        Binding("ctrl+c", "compress", "压缩", show=True),
        Binding("ctrl+d", "decompress", "解压", show=True),
        Binding("ctrl+p", "parallel", "并行压缩", show=True),
        Binding("ctrl+o", "open_folder", "打开目录", show=True),
    ]

    selected_path: reactive[str] = reactive("")
    mode: str = "compress"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                Label("📁 文件浏览器"),
                DirectoryTree(os.path.expanduser("~"), id="tree"),
                Label("🛡️ BombGuard"),
                Switch(value=True, id="bomb-guard"),
                id="sidebar",
            ),
            Vertical(
                Vertical(
                    Label("", id="info-path", classes="path"),
                    Label("", id="info-size", classes="size"),
                    Label("", id="info-ratio", classes="ratio"),
                    id="info",
                ),
                ProgressBar(total=100, show_eta=False, id="progress"),
                Vertical(
                    Horizontal(
                        Button("⚡ 压缩 (ctrl+c)", variant="success", id="btn-compress"),
                        Button("📂 解压 (ctrl+d)", variant="warning", id="btn-decompress"),
                    ),
                    Horizontal(
                        Button("🚀 并行压缩 (ctrl+p)", variant="primary", id="btn-parallel"),
                        Button("📁 打开目录 (ctrl+o)", id="btn-open"),
                    ),
                    id="actions",
                ),
                id="main",
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#progress", ProgressBar).display = False

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.selected_path = str(event.path)
        st = os.stat(self.selected_path)
        info_path = self.query_one("#info-path", Label)
        info_path.update(f"📄 {self.selected_path}")
        info_size = self.query_one("#info-size", Label)
        info_size.update(f"大小: {self._fsize(st.st_size)}")
        self.query_one("#info-ratio", Label).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        if btn == "btn-compress": self.action_compress()
        elif btn == "btn-decompress": self.action_decompress()
        elif btn == "btn-parallel": self.action_parallel()
        elif btn == "btn-open": self.action_open_folder()

    def action_compress(self) -> None: self._run(False, False)
    def action_decompress(self) -> None: self._run(True, False)
    def action_parallel(self) -> None: self._run(False, True)

    def action_open_folder(self) -> None:
        d = os.path.dirname(self.selected_path) if self.selected_path else os.path.expanduser("~")
        try: os.startfile(d)
        except Exception: self.notify(f"目录: {d}", title="📁")

    def _run(self, decompress: bool, parallel: bool) -> None:
        path = self.selected_path
        if not path or not os.path.isfile(path):
            self.notify("请先在左侧文件浏览器中选择文件", title="❌", severity="error")
            return

        prog = self.query_one("#progress", ProgressBar)
        prog.display = True; prog.update(progress=0)

        def worker():
            try:
                d = os.path.dirname(path)
                name = os.path.basename(path)
                if decompress:
                    out = os.path.join(d, name.replace(".hcf", ""))
                    reg = PluginRegistry()
                    guard = self.query_one("#bomb-guard", Switch).value
                    if guard: reg.discover_builtin()
                    stats = decompress(path, out, DecompressConfig(registry=reg))
                    self.app.call_from_thread(lambda: self._done(stats.original_size, 0, name))
                elif parallel:
                    out = os.path.join(d, name + ".hcf")
                    r = compress_parallel(path, out, level=6, workers=4)
                    self.app.call_from_thread(lambda: self._done(r["original_size"], r["compressed_size"], name))
                else:
                    out = os.path.join(d, name + ".hcf")
                    stats = compress(path, out, CompressConfig(level=6))
                    self.app.call_from_thread(lambda: self._done(stats.original_size, stats.compressed_size, name))
            except Exception as e:
                self.app.call_from_thread(lambda: self.notify(str(e), title="❌ 错误", severity="error"))
            finally:
                self.app.call_from_thread(lambda: setattr(prog, 'display', False))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, orig: int, comp: int, name: str) -> None:
        info_ratio = self.query_one("#info-ratio", Label)
        if comp > 0:
            ratio = comp * 100 / orig
            info_ratio.update(f"压缩率: {ratio:.1f}% (省 {(100-ratio):.1f}%)")
        else:
            info_ratio.update(f"解压完成: {self._fsize(orig)}")
        prog = self.query_one("#progress", ProgressBar)
        prog.update(progress=100)
        self.notify(f"{name} → {self._fsize(orig)} → {self._fsize(comp)}", title="✅ 完成")

    @staticmethod
    def _fsize(n: int) -> str:
        for u in ("B", "KB", "MB", "GB"):
            if abs(n) < 1024: return f"{n:.1f} {u}"
            n /= 1024
        return f"{n:.1f} TB"


def main() -> None:
    HcompressTUI().run()


if __name__ == "__main__":
    main()
