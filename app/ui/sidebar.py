"""Sidebar — clean rebuild with theme-aware text logo.

Collapsed (52px):  square logo icon only
Expanded (220px):  square logo + compressly-darkmode.png or compressly-lightmode.png
                   depending on the active theme
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSettings,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_COLLAPSED_W = 52
_EXPANDED_W  = 220
_ANIM_MS     = 160
_ROW_H       = 40
_ACCENT      = QColor("#d4956a")
_ACCENT_LIGHT = QColor("#b5714a")

# Theme-aware colors — updated by Sidebar.set_theme()
_ACTIVE_BG    = QColor(255, 255, 255, 14)
_HOVER_BG     = QColor(255, 255, 255, 8)
_ICON_IDLE    = QColor(255, 255, 255, 130)
_ICON_HOVER   = QColor(255, 255, 255, 180)
_LABEL_IDLE   = QColor(255, 255, 255, 140)
_LABEL_HOVER  = QColor(255, 255, 255, 180)
_LABEL_ACTIVE = QColor(255, 255, 255, 230)
_CREDIT_COLOR = QColor(255, 255, 255, 55)
_TEXT_H      = 22   # height in px for the text logo

# (key, icon, label, tooltip)
_NAV = [
    ("dashboard",  "⊡", "Compress",    "Compress images"),
    ("removebg",   "◎", "Remove BG",   "Background remover"),
    ("converter",  "⇄", "Convert",     "Image converter"),
    ("resizer",    "⤢", "Resize",      "Image resizer"),
    ("watermark",  "⊕", "Watermark",   "Add watermark"),
    ("exif",       "⊞", "EXIF",        "View & edit metadata"),
    ("gif",        "⊛", "GIF",         "GIF optimiser"),
    ("pdf",        "⊟", "PDF",         "PDF tools"),
    ("palette",    "◉", "Palette",     "Colour palette extractor"),
    ("metaclean",  "⊘", "Clean Meta",  "Batch metadata cleaner"),
    ("watch",      "◉", "Watch",       "Folder watch mode"),
    ("naming",     "⊜", "Naming",      "Custom output naming"),
    ("history",    "◫", "History",     "Compression history"),
    ("stats",      "◧", "Stats",       "Savings dashboard"),
    ("presets",    "◈", "Presets",     "Smart presets"),
    ("settings",   "⊙", "Settings",   "Preferences"),
    ("about",      "◌", "About",       "About Compressly"),
]


def _assets() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "assets"


def _load_text_logo(theme: str) -> QPixmap:
    """Load and scale the correct text logo for the given theme."""
    variant = "dark" if theme == "dark" else "light"
    path = _assets() / f"logo_text_{variant}.png"
    if not path.exists():
        # Fallback: try the old name
        path = _assets() / "logo_text.png"
    px = QPixmap(str(path))
    if px.isNull():
        return px
    # Scale to _TEXT_H tall, keep aspect ratio
    scaled_w = int(px.width() * _TEXT_H / px.height())
    return px.scaled(
        scaled_w, _TEXT_H,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Nav item — custom painted row
# ─────────────────────────────────────────────────────────────────────────────

class _NavItem(QWidget):
    """A single nav row — custom painted, entire area clickable."""

    clicked = Signal(str)

    def __init__(self, key: str, icon: str, label: str, tooltip: str) -> None:
        super().__init__()
        self._key     = key
        self._icon    = icon
        self._label   = label
        self._active  = False
        self._hovered = False
        self._expanded = False

        self.setFixedHeight(_ROW_H)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._icon_font  = QFont("Segoe UI Symbol", 15)
        self._label_font = QFont("Segoe UI Variable", 12)

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self.update()

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != expanded:
            self._expanded = expanded
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background highlight
        if self._active:
            p.fillRect(4, 2, w - 8, h - 4, _ACTIVE_BG)
            bar = QPainterPath()
            bar.addRoundedRect(4, 8, 3, h - 16, 2, 2)
            p.fillPath(bar, _ACCENT)
        elif self._hovered:
            p.fillRect(4, 2, w - 8, h - 4, _HOVER_BG)

        # Icon
        if self._active:
            icon_color = _ACCENT
        elif self._hovered:
            icon_color = _ICON_HOVER
        else:
            icon_color = _ICON_IDLE
        p.setPen(icon_color)
        p.setFont(self._icon_font)
        p.drawText(QRect(0, 0, 52, h), Qt.AlignmentFlag.AlignCenter, self._icon)

        # Label (expanded only)
        if self._expanded:
            if self._active:
                label_color = _LABEL_ACTIVE
            elif self._hovered:
                label_color = _LABEL_HOVER
            else:
                label_color = _LABEL_IDLE
            p.setPen(label_color)
            f = QFont(self._label_font)
            f.setWeight(QFont.Weight.DemiBold if self._active else QFont.Weight.Normal)
            p.setFont(f)
            p.drawText(QRect(52, 0, w - 60, h), Qt.AlignmentFlag.AlignVCenter, self._label)

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

class Sidebar(QFrame):
    nav_changed      = Signal(str)
    expanded_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        s = QSettings("Mistix", "Compressly")
        self._expanded: bool = s.value("sidebar_expanded", False, type=bool)
        self._active_key = "dashboard"
        self._current_theme = "dark"

        w = _EXPANDED_W if self._expanded else _COLLAPSED_W
        self.setMinimumWidth(w)
        self.setMaximumWidth(w)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(0)

        # ── Logo row ──────────────────────────────────────────────────────
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(10, 0, 10, 0)
        logo_row.setSpacing(8)

        # Square icon — always visible
        self._logo_icon = QLabel()
        self._logo_icon.setFixedSize(32, 32)
        self._logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        px = QPixmap(str(_assets() / "logo_small.png"))
        if not px.isNull():
            px = px.scaled(32, 32,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            self._logo_icon.setPixmap(px)
        else:
            self._logo_icon.setText("C")
            self._logo_icon.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self._logo_icon.setStyleSheet(
                "background-color:#d4956a;color:#1a1814;"
                "border-radius:8px;font-size:14px;font-weight:800;"
            )

        # Text logo — only visible when expanded, swaps with theme
        self._logo_text = QLabel()
        self._logo_text.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self._logo_text.setVisible(self._expanded)
        self._apply_text_logo("dark")   # default theme

        logo_row.addWidget(self._logo_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        logo_row.addWidget(self._logo_text, 0, Qt.AlignmentFlag.AlignVCenter)
        logo_row.addStretch(1)
        layout.addLayout(logo_row)
        layout.addSpacing(10)

        # ── Nav items ─────────────────────────────────────────────────────
        self._items: dict[str, _NavItem] = {}
        for key, icon, label, tooltip in _NAV:
            item = _NavItem(key, icon, label, tooltip)
            item.set_expanded(self._expanded)
            item.clicked.connect(self._on_item_clicked)
            self._items[key] = item
            layout.addWidget(item)

        layout.addStretch(1)

        # ── Credit ────────────────────────────────────────────────────────
        self._credit = QLabel("Made by Mistix")
        self._credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._credit.setStyleSheet(
            "color:rgba(255,255,255,0.18);font-size:9px;letter-spacing:0.5px;"
        )
        self._credit.setVisible(self._expanded)
        layout.addWidget(self._credit, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(6)

        # ── Toggle button ─────────────────────────────────────────────────
        self._toggle = QPushButton()
        self._toggle.setObjectName("sidebarToggle")
        self._toggle.setFixedSize(28, 28)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setToolTip(
            "Expand sidebar" if not self._expanded else "Collapse sidebar"
        )
        self._toggle.clicked.connect(self.toggle)
        self._update_toggle_icon()
        layout.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignCenter)

        # ── Animation ─────────────────────────────────────────────────────
        self._anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._anim.setDuration(_ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_anim_done)

        self.select("dashboard")
        # Apply initial theme colors after all widgets are created
        self._apply_nav_colors("dark")

    # ── public ────────────────────────────────────────────────────────────

    def select(self, key: str) -> None:
        self._active_key = key
        for k, item in self._items.items():
            item.set_active(k == key)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._start_anim()

    def set_theme(self, theme: str) -> None:
        """Call this whenever the app theme changes (dark / light)."""
        if theme == self._current_theme:
            return
        self._current_theme = theme
        self._apply_text_logo(theme)
        self._apply_nav_colors(theme)

    def _apply_nav_colors(self, theme: str) -> None:
        """Update module-level color constants for the nav items."""
        global _ACCENT, _ACTIVE_BG, _HOVER_BG
        global _ICON_IDLE, _ICON_HOVER
        global _LABEL_IDLE, _LABEL_HOVER, _LABEL_ACTIVE
        global _CREDIT_COLOR

        if theme == "light":
            _ACCENT      = _ACCENT_LIGHT
            _ACTIVE_BG   = QColor(0, 0, 0, 18)
            _HOVER_BG    = QColor(0, 0, 0, 10)
            _ICON_IDLE   = QColor(0, 0, 0, 110)
            _ICON_HOVER  = QColor(0, 0, 0, 160)
            _LABEL_IDLE  = QColor(0, 0, 0, 120)
            _LABEL_HOVER = QColor(0, 0, 0, 170)
            _LABEL_ACTIVE= QColor(0, 0, 0, 220)
            _CREDIT_COLOR= QColor(0, 0, 0, 80)
            self._credit.setStyleSheet(
                "color:rgba(0,0,0,0.30);font-size:9px;letter-spacing:0.5px;"
            )
        else:
            _ACCENT      = QColor("#d4956a")
            _ACTIVE_BG   = QColor(255, 255, 255, 18)
            _HOVER_BG    = QColor(255, 255, 255, 10)
            _ICON_IDLE   = QColor(255, 255, 255, 155)
            _ICON_HOVER  = QColor(255, 255, 255, 210)
            _LABEL_IDLE  = QColor(255, 255, 255, 165)
            _LABEL_HOVER = QColor(255, 255, 255, 210)
            _LABEL_ACTIVE= QColor(255, 255, 255, 245)
            _CREDIT_COLOR= QColor(255, 255, 255, 70)
            self._credit.setStyleSheet(
                "color:rgba(255,255,255,0.28);font-size:9px;letter-spacing:0.5px;"
            )

        # Repaint all nav items with new colors
        for item in self._items.values():
            item.update()

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    # ── internal ──────────────────────────────────────────────────────────

    def _apply_text_logo(self, theme: str) -> None:
        """Load and display the correct text logo for the given theme."""
        px = _load_text_logo(theme)
        if not px.isNull():
            self._logo_text.setPixmap(px)
            self._logo_text.setFixedSize(px.width(), px.height())
        else:
            # Fallback: plain text
            self._logo_text.clear()
            self._logo_text.setText("Compressly")
            color = "rgba(255,255,255,0.85)" if theme == "dark" else "rgba(0,0,0,0.80)"
            self._logo_text.setStyleSheet(
                f"color:{color};font-size:13px;font-weight:600;"
            )

    def _on_item_clicked(self, key: str) -> None:
        self.select(key)
        self.nav_changed.emit(key)

    def _update_toggle_icon(self) -> None:
        self._toggle.setText("›" if not self._expanded else "‹")

    def _start_anim(self) -> None:
        target = _EXPANDED_W if self._expanded else _COLLAPSED_W

        if self._expanded:
            self._logo_text.setVisible(True)
            self._credit.setVisible(True)
            for item in self._items.values():
                item.set_expanded(True)
            self.setMinimumWidth(0)

        self._anim.stop()
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(target)
        self._anim.start()

        self._update_toggle_icon()
        self._toggle.setToolTip(
            "Collapse sidebar" if self._expanded else "Expand sidebar"
        )
        QSettings("Mistix", "Compressly").setValue("sidebar_expanded", self._expanded)
        self.expanded_changed.emit(self._expanded)

    def _on_anim_done(self) -> None:
        target = _EXPANDED_W if self._expanded else _COLLAPSED_W
        if not self._expanded:
            self._logo_text.setVisible(False)
            self._credit.setVisible(False)
            for item in self._items.values():
                item.set_expanded(False)
        self.setMinimumWidth(target)
        self.setMaximumWidth(target)
