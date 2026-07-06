"""hcompress TUI — Textual-powered terminal interface."""

from __future__ import annotations

import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Button, Footer, Header, Input, Label, ListItem, ListView,
    ProgressBar, Static, Switch
)

from hcompress.engine import compress, decompress, CompressConfig, DecompressConfig, CompressStats, DecompressStats
from hcompress.plugins import PluginRegistry


class StatCard(Static):
    """A single stat display widget."""
    def __init__(self, label: str, value: str = "", color: str = "white") -> None:
        super().__init__()
        self._label = label
        self._value = value
        self._color = color

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="stat-label")
        yield Static(self._value, classes=f"stat-value {self._color}")

    def update_value(self, value: str) -> None:
        self.query(".stat-value").first().update(value)


class HcompressTUI(App[None]):
    """hcompress terminal UI."""

    CSS = """
    Screen { background: #0d0d14; }
    Header { background: #16162a; color: #6c8cff; }
    Footer { background: #16162a; }

    #sidebar {
        width: 32; background: #111122; border-right: solid #2a2a4a;
        padding: 0 1;
    }
    #sidebar Label { padding: 1 2; color: #888; text-style: bold; margin-top: 1; }
    #sidebar ListView { height: 1fr; }
    #sidebar ListItem {
        padding: 1 2; color: #aaa;
    }
    #sidebar ListItem.--highlight { background: #6c8cff22; color: #6c8cff; }

    #main { padding: 1 2; }
    #path-bar { height: 3; background: #16162a; padding: 0 2; margin-bottom: 1; }
    #path-bar Input { background: #0d0d14; border: solid #2a2a4a; }
    #file-list { height: 1fr; margin-bottom: 1; }
    #file-list ListItem { padding: 0 1; }
    #stats { height: 5; layout: horizontal; }
    #stats StatCard { width: 1fr; margin: 0 1; background: #16162a; padding: 1; }
    #progress { height: 3; margin-top: 1; background: #16162a; padding: 0 2; }
    #progress ProgressBar { margin: 1 0; }

    .stat-label { color: #666; text-style: bold; text-transform: uppercase; }
    .stat-value { text-style: bold; }
    .white { color: #eee; }
    .green { color: #3ec97e; }
    .blue { color: #6c8cff; }
    .yellow { color: #e5b83c; }
    .red { color: #e5535b; }

    Button { margin: 0 1; }
    Button.success { background: #3ec97e; color: #0d0d14; }
    Button.primary { background: #6c8cff; color: #fff; }
    Button.danger { background: #e5535b; color: #fff; }

    Horizontal Button { width: 1fr; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", show=True),
        Binding("ctrl+o", "pick_file", "选择文件", show=True),
        Binding("ctrl+c", "compress", "压缩", show=True),
        Binding("ctrl+d", "decompress", "解压", show=True),
        Binding("ctrl+k", "open_dir", "打开文件夹", show=True),
    ]

    files: reactive[list[str]] = reactive([])
    mode: str = "compress"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                Label("📦 模式"),
                ListView(
                    ListItem(Static("  ⚡ 压缩")),
                    ListItem(Static("  📂 解压")),
                    id="mode-list",
                ),
                Label("📁 文件"),
                ListView(id="file-list"),
                Label("🛡️ BombGuard"),
                Switch(value=True, id="bomb-guard"),
                id="sidebar",
            ),
            Vertical(
                Horizontal(
                    Input(placeholder="📂 文件路径...", id="path-input"),
                    Button("选择文件", variant="default", id="btn-pick"),
                    id="path-bar",
                ),
                ListView(id="file-list"),
                Horizontal(
                    StatCard("原始大小", "—", "white"),
                    StatCard("压缩后", "—", "blue"),
                    StatCard("压缩率", "—", "green"),
                    id="stats",
                ),
                Horizontal(
                    Button("⚡ 开始压缩", variant="success", id="btn-go"),
                    id="btn-row",
                ),
                ProgressBar(total=100, show_eta=False, id="progress"),
                id="main",
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#progress", ProgressBar).display = False

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "mode-list":
            self.mode = "compress" if event.item_index == 0 else "decompress"
            btn = self.query_one("#btn-go", Button)
            btn.label = "⚡ 开始压缩" if self.mode == "compress" else "📂 开始解压"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pick":
            self.app.action_pick_file()
        elif event.button.id == "btn-go":
            if self.mode == "compress":
                self.app.action_compress()
            else:
                self.app.action_decompress()

    def action_pick_file(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="选择文件")
        if path:
            path_input = self.query_one("#path-input", Input)
            path_input.value = path
            self._add_file(path)

    def _add_file(self, path: str) -> None:
        name = os.path.basename(path)
        size = os.path.getsize(path)
        self.query_one("#file-list", ListView).append(
            ListItem(Static(f"  {name}  ({self._fsize(size)})"))
        )
        self.query_one("#stats").query_one(StatCard).update_value(self._fsize(size))
        self.query_one("#stats").query(StatCard)[1].update_value("计算中...")

    def action_compress(self) -> None:
        path = self.query_one("#path-input", Input).value.strip()
        if not path or not os.path.isfile(path): return
        self._run_op(path, decompress=False)

    def action_decompress(self) -> None:
        path = self.query_one("#path-input", Input).value.strip()
        if not path or not os.path.isfile(path): return
        reg = PluginRegistry(); reg.discover_builtin()
        self._run_op(path, decompress=True, registry=reg)

    def _run_op(self, path: str, decompress: bool = False, registry=None) -> None:
        prog = self.query_one("#progress", ProgressBar)
        prog.display = True; prog.update(progress=0)

        import threading
        def worker():
            try:
                out = path + ("" if decompress else ".hcf")
                if decompress:
                    cfg = DecompressConfig(registry=registry) if registry else DecompressConfig()
                    stats = decompress(path, out, cfg)
                    self.app.call_from_thread(lambda: self._show_result(
                        stats.original_size, 0, 0, "解压完成"))
                else:
                    cfg = CompressConfig(level=6)
                    stats = compress(path, out, cfg)
                    ratio = stats.ratio * 100
                    self.app.call_from_thread(lambda: self._show_result(
                        stats.original_size, stats.compressed_size, ratio, "压缩完成"))
                self.app.call_from_thread(lambda: self.query_one("#progress", ProgressBar).update(progress=100))
            except Exception as e:
                self.app.call_from_thread(lambda: self._show_error(str(e)))
            finally:
                self.app.call_from_thread(lambda: prog.display if not prog.display else None)

        threading.Thread(target=worker, daemon=True).start()

    def _show_result(self, orig: int, comp: int, ratio: float, label: str) -> None:
        cards = self.query_one("#stats").query(StatCard)
        cards[0].update_value(self._fsize(orig))
        cards[1].update_value(self._fsize(comp))
        cards[2].update_value(f"{ratio:.1f}%" if ratio > 0 else "—")
        self.bell()
        self.notify(f"{label}！{self._fsize(orig)} → {self._fsize(comp)}", title="✅")

    def _show_error(self, msg: str) -> None:
        self.notify(msg, title="❌ 错误", severity="error")

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
