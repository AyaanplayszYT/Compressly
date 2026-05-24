"""Debug: simulate actual mouse click events (not btn.click()) on sidebar buttons."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer, Qt, QPoint, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app.theme import build_stylesheet, get_theme
from app.ui.main_window import MainWindow

results = []

def send_click(widget, pos_local=None):
    """Send a real press+release mouse event to a widget."""
    if pos_local is None:
        pos_local = widget.rect().center()
    global_pos = widget.mapToGlobal(pos_local)
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(pos_local),
        QPointF(global_pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(pos_local),
        QPointF(global_pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, press)
    QApplication.sendEvent(widget, release)

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet(get_theme()))

    win = MainWindow()
    win.show()
    sb = win._sidebar

    def on_nav(key):
        results.append(key)
        print(f"  nav_changed: {key}")

    sb.nav_changed.connect(on_nav)

    def run():
        sb.toggle()

        def test():
            print(f"\n=== EXPANDED (width={sb.width()}) ===")
            print("Sending real mouse events to row widgets:")
            for key, row_w in sb._nav_rows.items():
                print(f"  clicking row for {key}")
                send_click(row_w)

            print(f"\nSending real mouse events directly to buttons:")
            for key, btn in sb._nav_btns.items():
                print(f"  clicking btn for {key}")
                send_click(btn)

            print(f"\nResults: {results}")
            QTimer.singleShot(200, app.quit)

        QTimer.singleShot(400, test)

    QTimer.singleShot(200, run)
    app.exec()

if __name__ == "__main__":
    main()
