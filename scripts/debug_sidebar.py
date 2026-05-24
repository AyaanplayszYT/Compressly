"""Debug: test sidebar nav buttons in both collapsed and expanded states."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication
from app.theme import build_stylesheet, get_theme
from app.ui.sidebar import Sidebar

results = []

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet(get_theme()))

    sb = Sidebar()
    sb.show()

    def on_nav(key):
        results.append(key)
        print(f"  nav_changed emitted: {key}")

    sb.nav_changed.connect(on_nav)

    def run_tests():
        print("\n=== COLLAPSED STATE ===")
        for key, btn in sb._nav_btns.items():
            print(f"  clicking {key} btn (checkable={btn.isCheckable()}, enabled={btn.isEnabled()}, visible={btn.isVisible()})")
            btn.click()

        print("\n=== EXPANDING ===")
        sb.toggle()

        def test_expanded():
            print("\n=== EXPANDED STATE ===")
            for key, btn in sb._nav_btns.items():
                print(f"  clicking {key} btn (checkable={btn.isCheckable()}, enabled={btn.isEnabled()}, visible={btn.isVisible()}, parent={btn.parent()})")
                btn.click()

            print(f"\nResults: {results}")
            expected = ['dashboard','presets','settings','about',
                        'dashboard','presets','settings','about']
            ok = len(results) == 8
            print(f"PASS: {ok}  (got {len(results)} signals, expected 8)")
            QTimer.singleShot(200, app.quit)

        QTimer.singleShot(300, test_expanded)

    QTimer.singleShot(100, run_tests)
    app.exec()

if __name__ == "__main__":
    main()
