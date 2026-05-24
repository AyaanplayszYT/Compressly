"""Debug: check if MainWindow.mousePressEvent eats clicks on sidebar buttons."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app.theme import build_stylesheet, get_theme
from app.ui.main_window import MainWindow, _BORDER, _Edge

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet(get_theme()))

    win = MainWindow()
    win.show()
    sb = win._sidebar

    def run():
        # Expand sidebar
        sb.toggle()

        def check():
            print(f"\nSidebar width: {sb.width()}")
            print(f"Window pos: {win.pos()}")
            print(f"_BORDER: {_BORDER}")

            # Check each nav button's global position
            for key, btn in sb._nav_btns.items():
                global_center = btn.mapToGlobal(btn.rect().center())
                # Convert to window-local coords
                win_local = win.mapFromGlobal(global_center)
                edge = win._edge_at(win_local)
                print(f"  {key}: global={global_center} win_local={win_local} "
                      f"edge={edge} (NONE={_Edge.NONE})")
                if edge != _Edge.NONE:
                    print(f"    *** BUG: MainWindow._edge_at returns {edge} for this button! ***")
                    print(f"    *** This means mousePressEvent will intercept the click! ***")

            QTimer.singleShot(200, app.quit)

        QTimer.singleShot(300, check)

    QTimer.singleShot(200, run)
    app.exec()

if __name__ == "__main__":
    main()
