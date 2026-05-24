"""Custom frameless title bar — theme-aware, drag-to-snap safe.

Drag behaviour:
  • Dragging while normal  → moves the window normally.
  • Dragging while maximized → restores the window first, then positions it
    so the cursor stays under the title bar (standard Windows behaviour).
  • Dragging to the top of the screen → Windows detects y≈0 and offers the
    Aero Snap overlay; releasing snaps to fullscreen. This works because we
    do NOT fight the OS — we just move the window and let Windows decide.
  • Double-click → toggle maximized / normal.
  • The □ button updates its symbol to reflect the current state.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

# ── Theme color sets ──────────────────────────────────────────────────────────

_DARK = {
    "dextop":  "color: rgba(255,255,255,0.22); font-size: 10px; font-weight: 600; letter-spacing: 2px;",
    "sep":     "color: rgba(255,255,255,0.15); font-size: 11px; margin: 0 6px;",
    "appname": "color: rgba(255,255,255,0.55); font-size: 12px; font-weight: 500;",
    "status":  "color: rgba(255,255,255,0.28); font-size: 11px;",
    "dot_idle":"color: rgba(90,158,111,0.70); font-size: 8px;",
    "dot_run1":"color: rgba(212,149,106,0.95); font-size: 8px;",
    "dot_run2":"color: rgba(212,149,106,0.35); font-size: 8px;",
    "dot_done":"color: rgba(212,149,106,0.90); font-size: 8px;",
    "lbl_run1":"color: rgba(212,149,106,0.75); font-size: 11px;",
    "lbl_run2":"color: rgba(255,255,255,0.28); font-size: 11px;",
    "lbl_done":"color: rgba(212,149,106,0.80); font-size: 11px;",
}

_LIGHT = {
    "dextop":  "color: rgba(0,0,0,0.30); font-size: 10px; font-weight: 600; letter-spacing: 2px;",
    "sep":     "color: rgba(0,0,0,0.20); font-size: 11px; margin: 0 6px;",
    "appname": "color: rgba(0,0,0,0.55); font-size: 12px; font-weight: 500;",
    "status":  "color: rgba(0,0,0,0.35); font-size: 11px;",
    "dot_idle":"color: rgba(40,120,70,0.80); font-size: 8px;",
    "dot_run1":"color: rgba(160,100,50,0.95); font-size: 8px;",
    "dot_run2":"color: rgba(160,100,50,0.35); font-size: 8px;",
    "dot_done":"color: rgba(160,100,50,0.90); font-size: 8px;",
    "lbl_run1":"color: rgba(160,100,50,0.80); font-size: 11px;",
    "lbl_run2":"color: rgba(0,0,0,0.35); font-size: 11px;",
    "lbl_done":"color: rgba(160,100,50,0.80); font-size: 11px;",
}

# How many pixels the cursor must move before we start dragging.
# This prevents accidental un-maximize on a simple click.
_DRAG_THRESHOLD = 5


class TitleBar(QWidget):
    close_clicked  = Signal()
    min_clicked    = Signal()
    max_clicked    = Signal()
    sidebar_toggle = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(38)

        self._window: QWidget | None = None
        self._colors = _DARK
        self._pulse_state = False

        # Drag state
        self._press_pos: QPoint | None = None      # where the mouse was pressed (global)
        self._dragging = False                      # True once threshold is exceeded
        self._was_maximized = False                 # was the window maximized at press time?
        self._restore_offset_ratio = 0.5           # cursor x as fraction of title bar width

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(0)

        # ── Left ──────────────────────────────────────────────────────────
        self._sidebar_btn = QPushButton("≡")
        self._sidebar_btn.setObjectName("winBtn")
        self._sidebar_btn.setFixedSize(38, 38)
        self._sidebar_btn.setToolTip("Toggle sidebar  (Ctrl+\\)")
        self._sidebar_btn.clicked.connect(self.sidebar_toggle.emit)
        layout.addWidget(self._sidebar_btn)

        self._dextop  = QLabel("DEXTOP")
        self._sep     = QLabel("·")
        self._appname = QLabel("Compressly")
        layout.addWidget(self._dextop)
        layout.addWidget(self._sep)
        layout.addWidget(self._appname)
        layout.addStretch(1)

        # ── Centre: status ────────────────────────────────────────────────
        self._dot   = QLabel("●")
        self._label = QLabel("Ready")
        layout.addWidget(self._dot)
        layout.addSpacing(5)
        layout.addWidget(self._label)
        layout.addStretch(1)

        # ── Right: window controls ────────────────────────────────────────
        self._max_btn = None
        for symbol, tip, sig_name, is_close in (
            ("─", "Minimise",         "min_clicked",   False),
            ("□", "Maximise/Restore", "max_clicked",   False),
            ("✕", "Close",            "close_clicked", True),
        ):
            btn = QPushButton(symbol)
            btn.setObjectName("winBtn")
            if is_close:
                btn.setProperty("closeBtn", "true")
            btn.setFixedSize(38, 38)
            btn.setToolTip(tip)
            btn.clicked.connect(getattr(self, sig_name).emit)
            layout.addWidget(btn)
            if sig_name == "max_clicked":
                self._max_btn = btn

        # Pulse timer
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(700)
        self._pulse_timer.timeout.connect(self._pulse)

        self._apply_colors()

    # ── public ────────────────────────────────────────────────────────────

    def set_window(self, win: QWidget) -> None:
        self._window = win

    def set_theme(self, theme: str) -> None:
        self._colors = _LIGHT if theme == "light" else _DARK
        self._apply_colors()

    def update_max_button(self, is_maximized: bool) -> None:
        """Update the □/❐ symbol to reflect the current window state."""
        if self._max_btn:
            self._max_btn.setText("❐" if is_maximized else "□")
            self._max_btn.setToolTip(
                "Restore" if is_maximized else "Maximise/Restore"
            )

    def set_status_idle(self) -> None:
        self._pulse_timer.stop()
        self._pulse_state = False
        c = self._colors
        self._dot.setStyleSheet(c["dot_idle"])
        self._label.setText("Ready")
        self._label.setStyleSheet(c["status"])

    def set_status_running(self, label: str = "Compressing") -> None:
        self._label.setText(label)
        self._pulse_timer.start()

    def set_status_done(self, summary: str) -> None:
        self._pulse_timer.stop()
        c = self._colors
        self._dot.setStyleSheet(c["dot_done"])
        self._label.setText(summary)
        self._label.setStyleSheet(c["lbl_done"])
        QTimer.singleShot(4000, self.set_status_idle)

    # ── drag ──────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._window:
            self._press_pos = event.globalPosition().toPoint()
            self._dragging = False
            self._was_maximized = self._window.isMaximized()
            # Remember where in the title bar the user clicked (0.0–1.0)
            # so we can restore the window under the cursor.
            bar_w = max(1, self.width())
            self._restore_offset_ratio = event.position().x() / bar_w
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press_pos is None or self._window is None:
            super().mouseMoveEvent(event)
            return

        current = event.globalPosition().toPoint()
        delta = current - self._press_pos

        # Only start dragging once the cursor has moved past the threshold.
        # This prevents a simple click from accidentally un-maximizing.
        if not self._dragging:
            if (abs(delta.x()) < _DRAG_THRESHOLD
                    and abs(delta.y()) < _DRAG_THRESHOLD):
                super().mouseMoveEvent(event)
                return
            self._dragging = True

        if self._was_maximized:
            # Restore the window first, then position it so the cursor
            # stays under the same relative point in the title bar.
            self._window.showNormal()
            self._was_maximized = False

            # Place the window so the cursor is at the same x-fraction
            # of the title bar as when the user pressed.
            win_w = self._window.width()
            cursor_x_in_bar = int(win_w * self._restore_offset_ratio)
            new_x = current.x() - cursor_x_in_bar
            new_y = current.y() - self.height() // 2
            self._window.move(new_x, new_y)
            # Update press_pos so the next delta is relative to here
            self._press_pos = current
        else:
            self._window.move(self._window.pos() + delta)
            self._press_pos = current

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press_pos = None
        self._dragging = False
        self._was_maximized = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._window:
            if self._window.isMaximized():
                self._window.showNormal()
            else:
                self._window.showMaximized()
        super().mouseDoubleClickEvent(event)

    # ── internal ──────────────────────────────────────────────────────────

    def _apply_colors(self) -> None:
        c = self._colors
        self._dextop.setStyleSheet(c["dextop"])
        self._sep.setStyleSheet(c["sep"])
        self._appname.setStyleSheet(c["appname"])
        self._label.setStyleSheet(c["status"])
        self._dot.setStyleSheet(c["dot_idle"])

    def _pulse(self) -> None:
        self._pulse_state = not self._pulse_state
        c = self._colors
        if self._pulse_state:
            self._dot.setStyleSheet(c["dot_run1"])
            self._label.setStyleSheet(c["lbl_run1"])
        else:
            self._dot.setStyleSheet(c["dot_run2"])
            self._label.setStyleSheet(c["lbl_run2"])
