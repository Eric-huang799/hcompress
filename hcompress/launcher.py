"""hcompress launcher — GUI by default, CLI with arguments.

Bundled entry point for PyInstaller .exe packaging.
Double-click → GUI.  Command-line args → CLI.
"""

import os
import sys

# When bundled by PyInstaller, the C extension DLL is next to the exe.
# Add that directory to PATH so ctypes can find it.
if getattr(sys, "frozen", False):
    os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")

    # Force UTF-8 on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> None:
    if len(sys.argv) > 1:
        # CLI mode
        from hcompress.cli import main as cli_main
        cli_main()
    else:
        # GUI mode (double-click)
        from hcompress.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
