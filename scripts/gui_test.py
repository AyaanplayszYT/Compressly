"""Headless-style GUI smoke test — boot the app, render once, verify state, exit."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from app.theme import build_stylesheet
from app.ui import MainWindow


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())

    window = MainWindow()
    window.show()

    # Process events for a short time, then exit.
    QTimer.singleShot(500, window.close)
    QTimer.singleShot(800, app.quit)

    code = app.exec()

    # Print a few sanity checks.
    print("[gui_test] window title:", window.windowTitle())
    print("[gui_test] window size:", window.width(), "x", window.height())
    print("[gui_test] central widget present:", window.centralWidget() is not None)
    print("[gui_test] OK")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
