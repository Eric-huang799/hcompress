"""hcompress GUI — 图形化压缩/解压工具.

tkinter 原生界面，零额外依赖。
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path


class HcompressGUI:
    """Main GUI window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("hcompress — Canonical Huffman 压缩工具")
        self.root.geometry("580x520")
        self.root.resizable(False, False)
        self._center_window()

        # Catppuccin Mocha palette
        self.BG = "#1e1e2e"
        self.CARD = "#313244"
        self.FG = "#cdd6f4"
        self.ACCENT = "#89b4fa"
        self.GREEN = "#a6e3a1"
        self.YELLOW = "#f9e2af"
        self.RED = "#f38ba8"
        self.SUBTLE = "#6c7086"

        self.root.configure(bg=self.BG)
        self.input_file: str = ""
        self.output_file: str = ""

        self._build()
        self.root.mainloop()

    # ── UI build ────────────────────────────────────────────────────────

    def _build(self) -> None:
        bg, fg, accent, card, green = self.BG, self.FG, self.ACCENT, self.CARD, self.GREEN

        # Title
        tk.Label(self.root, text="hcompress", font=("Segoe UI", 24, "bold"),
                 fg=accent, bg=bg).pack(pady=(24, 0))
        tk.Label(self.root, text="Canonical Huffman 压缩 / 解压工具",
                 font=("Segoe UI", 10), fg=fg, bg=bg).pack(pady=(0, 16))

        # ── Mode ──
        self.mode_var = tk.StringVar(value="compress")
        mf = tk.Frame(self.root, bg=bg)
        mf.pack(pady=4)
        tk.Radiobutton(mf, text="📦  压缩", variable=self.mode_var, value="compress",
                       font=("Segoe UI", 12), fg=fg, bg=bg, selectcolor=bg,
                       activebackground=bg, activeforeground=accent,
                       command=self._on_mode).pack(side=tk.LEFT, padx=20)
        tk.Radiobutton(mf, text="📂  解压", variable=self.mode_var, value="decompress",
                       font=("Segoe UI", 12), fg=fg, bg=bg, selectcolor=bg,
                       activebackground=bg, activeforeground=accent,
                       command=self._on_mode).pack(side=tk.LEFT, padx=20)

        # ── Input file ──
        tk.Label(self.root, text="输入文件", font=("Segoe UI", 10, "bold"),
                 fg=fg, bg=bg).pack(pady=(16, 4))
        inf = tk.Frame(self.root, bg=bg)
        inf.pack(padx=40, fill=tk.X)
        self.in_entry = tk.Entry(inf, font=("Segoe UI", 10), bg=card, fg=fg,
                                  relief=tk.FLAT, insertbackground=fg)
        self.in_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(inf, text="选择文件", command=self._pick_input,
                  font=("Segoe UI", 9), bg=card, fg=fg, relief=tk.FLAT,
                  padx=12, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(6, 0))

        # ── Output file ──
        tk.Label(self.root, text="输出路径", font=("Segoe UI", 10, "bold"),
                 fg=fg, bg=bg).pack(pady=(10, 4))
        ouf = tk.Frame(self.root, bg=bg)
        ouf.pack(padx=40, fill=tk.X)
        self.out_entry = tk.Entry(ouf, font=("Segoe UI", 10), bg=card, fg=fg,
                                   relief=tk.FLAT, insertbackground=fg)
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(ouf, text="浏览", command=self._pick_output,
                  font=("Segoe UI", 9), bg=card, fg=fg, relief=tk.FLAT,
                  padx=12, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(6, 0))

        # ── Level (compress only) ──
        self.lv_frame = tk.Frame(self.root, bg=bg)
        self.lv_frame.pack(pady=(8, 0))
        tk.Label(self.lv_frame, text="压缩级别", font=("Segoe UI", 10),
                 fg=fg, bg=bg).pack(side=tk.LEFT)
        self.level_var = tk.IntVar(value=6)
        self.level_scale = tk.Scale(
            self.lv_frame, from_=0, to=9, orient=tk.HORIZONTAL,
            variable=self.level_var, font=("Segoe UI", 8), bg=card, fg=fg,
            troughcolor=bg, relief=tk.FLAT, length=260, highlightthickness=0,
        )
        self.level_scale.pack(side=tk.LEFT, padx=10)
        self.lv_label = tk.Label(self.lv_frame, text="6", font=("Segoe UI", 10, "bold"),
                                  fg=accent, bg=bg, width=2)
        self.lv_label.pack(side=tk.LEFT)

        # Live update level label
        def _on_level(*_):
            self.lv_label.config(text=str(self.level_var.get()))
            self.level_var.trace_add("write", _on_level)

        self.level_var.trace_add("write", _on_level)

        # ── Go button ──
        self.go_btn = tk.Button(
            self.root, text="开始压缩", command=self._start,
            font=("Segoe UI", 13, "bold"), bg=green, fg="#1e1e2e",
            relief=tk.FLAT, padx=50, pady=8, cursor="hand2",
        )
        self.go_btn.pack(pady=14)

        # ── Progress ──
        self.progress = ttk.Progressbar(self.root, mode="indeterminate", length=460)
        self.progress.pack(pady=(0, 4))

        # ── Status ──
        self.status_label = tk.Label(self.root, text="就绪 — 选择文件后点击开始",
                                      font=("Segoe UI", 9), fg=self.SUBTLE, bg=bg)
        self.status_label.pack()

        # ── Result ──
        self.result_text = tk.Text(
            self.root, font=("Cascadia Code", 9), bg=card, fg=fg, relief=tk.FLAT,
            height=7, state=tk.DISABLED, wrap=tk.WORD, borderwidth=0,
        )
        self.result_text.pack(pady=(10, 0), padx=40, fill=tk.X)

    # ── actions ─────────────────────────────────────────────────────────

    def _on_mode(self) -> None:
        if self.mode_var.get() == "compress":
            self.lv_frame.pack(pady=(8, 0))
            self.go_btn.config(text="开始压缩", bg=self.GREEN)
        else:
            self.lv_frame.pack_forget()
            self.go_btn.config(text="开始解压", bg=self.YELLOW)

    def _pick_input(self) -> None:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if self.mode_var.get() == "decompress":
            path = filedialog.askopenfilename(
                title="选择 HCF 压缩文件",
                initialdir=desktop,
                filetypes=[("HCF 文件", "*.hcf"), ("所有文件", "*.*")],
            )
        else:
            path = filedialog.askopenfilename(
                title="选择要压缩的文件",
                initialdir=desktop,
            )
        if path:
            self._set_input(path)

    def _pick_output(self) -> None:
        """Browse for output *folder*, combine with auto-generated filename."""
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        folder = filedialog.askdirectory(
            title="选择保存位置",
            initialdir=desktop,
        )
        if not folder:
            return
        # Use the filename portion from the current entry (or generate one)
        current = self.out_entry.get().strip()
        if current:
            fname = os.path.basename(current)
        elif self.input_file:
            in_name = os.path.basename(self.input_file)
            fname = in_name + ".hcf" if self.mode_var.get() == "compress" else in_name
        else:
            fname = "output.hcf"
        path = os.path.join(folder, fname)
        self._set_output(path)

    def _set_output(self, path: str) -> None:
        self.out_entry.delete(0, tk.END)
        self.out_entry.insert(0, path)
        self.output_file = path

    def _set_input(self, path: str) -> None:
        self.input_file = path
        self.in_entry.delete(0, tk.END)
        self.in_entry.insert(0, path)
        # Auto-suggest output — keep original extension, append .hcf
        p = Path(path)
        if self.mode_var.get() == "compress":
            out = str(p) + ".hcf"     # foo.jpg → foo.jpg.hcf (保留原后缀)
        else:
            if p.suffix.lower() == ".hcf":
                out = str(p.with_suffix(""))     # foo.jpg.hcf → foo.jpg
            else:
                out = str(p) + ".out"
        self.out_entry.delete(0, tk.END)
        self.out_entry.insert(0, out)
        self.output_file = out
        self.status_label.config(text=f"已选择: {os.path.basename(path)}  ({self._fsize(os.path.getsize(path))})",
                                 fg=self.GREEN)

    def _start(self) -> None:
        path = self.in_entry.get().strip()
        out = self.out_entry.get().strip()
        if not path:
            messagebox.showwarning("提示", "请先选择输入文件")
            return
        if not out:
            messagebox.showwarning("提示", "请指定输出路径")
            return
        if not os.path.exists(path):
            messagebox.showerror("错误", f"文件不存在:\n{path}")
            return

        self.input_file = path
        self.output_file = out

        self.go_btn.config(state=tk.DISABLED)
        self.progress.start(8)
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.config(state=tk.DISABLED)
        mode = self.mode_var.get()
        self.status_label.config(
            text=f"{'压缩' if mode == 'compress' else '解压'}中...", fg=self.YELLOW)

        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self) -> None:
        from hcompress.engine import compress, decompress, CompressConfig, DecompressConfig

        mode = self.mode_var.get()
        try:
            if mode == "compress":
                cfg = CompressConfig(level=self.level_var.get())
                r = compress(self.input_file, self.output_file, cfg)
                summary = (
                    f"压缩完成!\n"
                    f"原始: {self._fsize(r.original_size)}\n"
                    f"压缩: {self._fsize(r.compressed_size)}\n"
                    f"比率: {r.ratio*100:.1f}%  (节省 {(1-r.ratio)*100:.1f}%)\n"
                    f"耗时: {r.elapsed_ms:.1f} ms"
                )
                ok = True
            else:
                cfg = DecompressConfig()
                r = decompress(self.input_file, self.output_file, cfg)
                summary = (
                    f"解压完成!\n"
                    f"大小: {self._fsize(r.original_size)}\n"
                    f"耗时: {r.elapsed_ms:.1f} ms\n"
                    f"校验: {'✓ 通过' if r.checksum_ok else '✗ 失败'}"
                )
                ok = r.checksum_ok
        except Exception as exc:
            ok = False
            summary = f"失败: {exc}"

        self.root.after(0, lambda: self._done(ok, summary))

    def _done(self, ok: bool, msg: str) -> None:
        self.progress.stop()
        self.go_btn.config(state=tk.NORMAL)
        mode = self.mode_var.get()
        self.go_btn.config(text="开始压缩" if mode == "compress" else "开始解压")
        self.status_label.config(text="✓ 完成" if ok else "✗ 失败",
                                 fg=self.GREEN if ok else self.RED)
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert("1.0", msg)
        self.result_text.config(state=tk.DISABLED)

    @staticmethod
    def _fsize(n: int) -> str:
        for u in ("B", "KB", "MB", "GB"):
            if abs(n) < 1024:
                return f"{n:.1f} {u}"
            n /= 1024
        return f"{n:.1f} TB"

    def _center_window(self) -> None:
        self.root.update_idletasks()
        w, h = 580, 520
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


def main() -> None:
    HcompressGUI()


if __name__ == "__main__":
    main()
