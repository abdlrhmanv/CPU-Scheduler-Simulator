#!/usr/bin/env python3
# Shebang: run this file with python3 when executed directly (e.g. ./main.py if executable).

"""Application entry: run from `cpu-schedular/` as `python main.py`."""
# Module docstring: documents that the working directory must be cpu-schedular/ for imports.

import os  # Access process environment (Qt plugin paths, platform selection).
import sys  # argv for QApplication and sys.path manipulation for package resolution.
from importlib.util import find_spec  # Locate PySide6 install path without importing Qt yet.
from pathlib import Path  # Build filesystem paths to src/, ui/, and PySide6 plugin dirs.

# Repo root = directory containing this file (cpu-schedular/)
_ROOT = Path(__file__).resolve().parent  # Absolute path to folder where main.py lives.
# Expose `engine` package (under src/) and `ui` package (sibling to src/)
if str(_ROOT / "src") not in sys.path:  # Only prepend if not already present (idempotent).
    sys.path.insert(0, str(_ROOT / "src"))  # So `import engine` resolves to src/engine/.
if str(_ROOT) not in sys.path:  # cpu-schedular/ must be on path for `import ui`.
    sys.path.insert(0, str(_ROOT))  # Prepend project root for top-level ui package.

# --- Qt on Linux: fix "Could not find the Qt platform plugin xcb" when the
#    platform plugin search path is empty (common with conda / some pip layouts).
#    Must run before importing PySide6.QtWidgets.
_spec = find_spec("PySide6")  # ModuleSpec for PySide6; .origin points to package __init__.py.
if _spec and _spec.origin:  # Guard: skip if PySide6 not installed or spec incomplete.
    _pyside_root = Path(_spec.origin).resolve().parent  # Directory containing PySide6 package.
    _qt_plugins = _pyside_root / "Qt" / "plugins"  # Standard wheel layout for Qt plugin roots.
    _platforms = _qt_plugins / "platforms"  # Subfolder holding libqwayland.so, libqxcb.so, etc.
    if _platforms.is_dir():  # If platform plugins exist, tell Qt where to find them.
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(_platforms))  # Don’t override user.
    if _qt_plugins.is_dir():  # Broader plugin path (imageformats, styles, etc.).
        os.environ.setdefault("QT_PLUGIN_PATH", str(_qt_plugins))  # Default Qt plugin search path.

# --- Linux / Qt platform
# Qt may pick Wayland and then fail with "Failed to create wl_display" in Cursor/IDE
# terminals, or after a leftover `export QT_QPA_PLATFORM=wayland` in the same shell.
# We default to X11 (xcb), which works with XWayland on Wayland desktops.
# To try native Wayland on a real session: USE_WAYLAND=1 python main.py
if sys.platform.startswith("linux"):  # Platform-specific GUI backend selection.
    if os.environ.get("USE_WAYLAND") == "1":  # Explicit opt-in to native Wayland from real sessions.
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland")  # Only set if not already set.
    else:  # Default: force X11 so IDE terminals and stale wayland exports don’t crash.
        os.environ["QT_QPA_PLATFORM"] = "xcb"  # Always override (fixes leftover shell exports).

from PySide6.QtWidgets import QApplication  # Must run after env vars above are applied.

from ui.main_window import MainWindow  # Top-level window with panels and simulation wiring.


def main() -> None:  # Entry point when run as script or imported for testing.
    app = QApplication(sys.argv)  # Qt application object; consumes CLI args (e.g. -style).
    win = MainWindow()  # Build UI: input, Gantt, burst table, metrics, controls.
    win.show()  # Display non-modal top-level window.
    sys.exit(app.exec())  # Run event loop until last window closes; pass exit code to OS.


if __name__ == "__main__":  # Only run main() when executed as __main__, not when imported.
    main()  # Start the GUI application.
