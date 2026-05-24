"""Debug: test sidebar nav in the full MainWindow context."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication
from app.theme import build_stylesheet, get_theme
from app.ui.main_window import MainWindow

results = []

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
        print("\n=== COLLAPSED ===")
        for key, btn in sb._nav_btns.items():
            btn.click()

        print("\n=== EXPANDING ===")
        sb.toggle()

        def test_expanded():
            print(f"\n=== EXPANDED (sidebar width={sb.width()}) ===")
            for key, btn in sb._nav_btns.items():
                geo = btn.geometry()
                global_pos = btn.mapToGlobal(btn.rect().center())
                print(f"  {key}: enabled={btn.isEnabled()} visible={btn.isVisible()} "
                      f"geo={geo} global_center={global_pos}")
                btn.click()

            print(f"\nResults: {results}")
            print(f"Expected 8 signals, got {len(results)}: {'PASS' if len(results)==8 else 'FAIL'}")
            QTimer.singleShot(300, app.quit)

        QTimer.singleShot(400, test_expanded)

    QTimer.singleShot(200, run)
    app.exec()

if __name__ == "__main__":
    main()
