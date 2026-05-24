"""Compressly desktop — entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from app import APP_ID, APP_NAME
from app.theme import build_stylesheet, get_theme
from app.ui import MainWindow


def _set_app_id() -> None:
    """Tell Windows to group taskbar icons under our AUMID.

    This is what makes Windows use our custom icon in the taskbar
    instead of the generic Python icon.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _resource(path: str) -> Path:
    """Resolve asset paths for both source and PyInstaller frozen builds."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / path


def _build_icon() -> QIcon:
    """Build a QIcon with all available sizes for crisp rendering everywhere."""
    icon = QIcon()
    assets = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets"

    # Add the ICO file (contains 16, 32, 48, 64, 128, 256 px)
    ico = assets / "icon.ico"
    if ico.exists():
        icon = QIcon(str(ico))

    # Also add the full 512px PNG for HiDPI displays
    png = assets / "icon.png"
    if png.exists():
        icon.addFile(str(png), mode=QIcon.Mode.Normal, state=QIcon.State.Off)

    return icon


def main() -> int:
    # Must be called BEFORE QApplication is created
    _set_app_id()

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Mistix")
    app.setApplicationDisplayName(APP_NAME)
    app.setStyle("Fusion")

    # Set the icon on the application — this is what the taskbar uses
    icon = _build_icon()
    app.setWindowIcon(icon)

    theme = get_theme()
    app.setStyleSheet(build_stylesheet(theme))

    window = MainWindow()
    # Also set on the window for the title bar / alt-tab thumbnail
    window.setWindowIcon(icon)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
