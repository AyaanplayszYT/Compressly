"""Secondary pages: Presets, Settings, About.

Every page has consistent 24px padding and a proper scroll area.
Cards use WA_StyledBackground so QSS backgrounds actually paint.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..models import OutputFormat, ResizeMode
from ..presets import PRESETS
from ..theme import get_pref, set_pref


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _surface() -> QFrame:
    """A surface card — slightly lighter than the bg."""
    f = QFrame()
    f.setObjectName("surface")
    f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return f


def _eyebrow(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("eyebrow")
    return lbl


def _sep() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet("background-color: rgba(255,255,255,0.07);")
    return w


def _scrollable(inner: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
    sa.setWidget(inner)
    return sa


def _page_layout(parent: QWidget) -> QVBoxLayout:
    """Standard page outer layout with 24px padding."""
    l = QVBoxLayout(parent)
    l.setContentsMargins(24, 20, 24, 20)
    l.setSpacing(16)
    return l


# ─────────────────────────────────────────────────────────────────────────────
# Presets page
# ─────────────────────────────────────────────────────────────────────────────

class PresetsPage(QWidget):
    preset_chosen = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scrollable content
        inner = QWidget()
        il = _page_layout(inner)

        # Page header
        il.addWidget(_eyebrow("PRESETS"))
        title = QLabel("One-click optimization recipes")
        title.setObjectName("h1")
        il.addWidget(title)
        sub = QLabel(
            "Pick a preset to instantly configure format, quality, and resize "
            "settings for your whole queue. Applied immediately."
        )
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        il.addWidget(sub)
        il.addWidget(_sep())

        # Grid of preset cards
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, preset in enumerate(PRESETS):
            grid.addWidget(self._preset_card(preset), i // 2, i % 2)
        il.addWidget(grid_w)
        il.addStretch(1)

        outer.addWidget(_scrollable(inner), 1)

    def _preset_card(self, preset) -> QFrame:
        card = _surface()
        l = QVBoxLayout(card)
        l.setContentsMargins(18, 16, 18, 16)
        l.setSpacing(10)

        # Header row: icon + name
        top = QHBoxLayout()
        top.setSpacing(12)
        icon = QLabel("◈")
        icon.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon.setStyleSheet(
            "font-size: 16px; color: #d4956a;"
            " background-color: rgba(212,149,106,0.12);"
            " border: 1px solid rgba(212,149,106,0.25);"
            " border-radius: 8px; padding: 5px 7px;"
        )
        icon.setFixedSize(34, 34)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = QLabel(preset.name)
        name.setObjectName("h3")
        top.addWidget(icon)
        top.addWidget(name, 1)
        l.addLayout(top)

        desc = QLabel(preset.description)
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        l.addWidget(desc)

        # Chips
        chips = QHBoxLayout()
        chips.setSpacing(6)
        fmt = preset.settings_overrides.get("output_format", OutputFormat.WEBP)
        q = preset.settings_overrides.get("quality", 80)
        rm = preset.settings_overrides.get("resize_mode", ResizeMode.NONE)
        if rm == ResizeMode.PERCENT:
            r_txt = f"{preset.settings_overrides.get('resize_percent', 100)}%"
        elif rm == ResizeMode.LONGEST:
            r_txt = f"{preset.settings_overrides.get('resize_longest', 1920)}px"
        else:
            r_txt = "Original"
        for txt in (fmt.display, f"Q{q}", r_txt):
            chip = QLabel(txt)
            chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            chip.setStyleSheet(
                "font-size: 10px; font-weight: 500; padding: 2px 8px;"
                " border-radius: 6px;"
                " background-color: rgba(255,255,255,0.06);"
                " border: 1px solid rgba(255,255,255,0.10);"
            )
            chips.addWidget(chip)
        chips.addStretch(1)
        l.addLayout(chips)

        btn = QPushButton("Apply preset")
        btn.setProperty("variant", "primary")
        btn.setFixedHeight(32)
        btn.clicked.connect(lambda _c, p=preset: self.preset_chosen.emit(p))
        l.addWidget(btn)
        return card


# ─────────────────────────────────────────────────────────────────────────────
# Settings page
# ─────────────────────────────────────────────────────────────────────────────

class SettingsPage(QWidget):
    theme_changed = Signal(str)

    def __init__(
        self, current_theme: str = "dark", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._theme = current_theme

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        inner = QWidget()
        il = _page_layout(inner)

        il.addWidget(_eyebrow("SETTINGS"))
        title = QLabel("Preferences")
        title.setObjectName("h1")
        il.addWidget(title)
        il.addWidget(_sep())

        il.addWidget(self._section(
            "Appearance",
            "Switch between dark and light themes.",
            self._build_theme_row(),
        ))
        il.addWidget(self._section(
            "Output naming",
            "Choose the suffix added to compressed filenames.",
            self._build_naming_row(),
        ))
        il.addWidget(self._section(
            "Privacy & security",
            "Compressly never uploads your files. All processing is local.",
            self._build_privacy_info(),
        ))
        il.addWidget(self._section(
            "About",
            f"Compressly v{__version__}  ·  MIT License  ·  PySide6 + Pillow",
            None,
        ))
        il.addStretch(1)

        outer.addWidget(_scrollable(inner), 1)

    def _section(self, title: str, subtitle: str, widget: QWidget | None) -> QFrame:
        card = _surface()
        l = QVBoxLayout(card)
        l.setContentsMargins(18, 16, 18, 16)
        l.setSpacing(10)
        t = QLabel(title)
        t.setObjectName("h3")
        l.addWidget(t)
        s = QLabel(subtitle)
        s.setObjectName("muted")
        s.setWordWrap(True)
        l.addWidget(s)
        if widget is not None:
            l.addWidget(_sep())
            l.addWidget(widget)
        return card

    def _build_theme_row(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._theme_group = QButtonGroup(w)
        self._theme_group.setExclusive(True)
        self._theme_btns: dict[str, QPushButton] = {}
        for key, label, desc in (
            ("dark",  "Dark",  "Charcoal + terracotta"),
            ("light", "Light", "Warm cream"),
        ):
            col = QVBoxLayout()
            col.setSpacing(4)
            btn = QPushButton(label)
            btn.setObjectName("chip")
            btn.setCheckable(True)
            btn.setChecked(key == self._theme)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda _c, k=key: self._on_theme(k))
            self._theme_group.addButton(btn)
            self._theme_btns[key] = btn
            sub = QLabel(desc)
            sub.setObjectName("dim")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(btn)
            col.addWidget(sub)
            row.addLayout(col, 1)
        return w

    def _build_naming_row(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(8)
        lbl = QLabel("Suffix appended to the output filename:")
        lbl.setObjectName("muted")
        l.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(6)
        suffix_pref = get_pref("output_suffix", "_compressed")
        self._suffix_group = QButtonGroup(w)
        self._suffix_group.setExclusive(True)
        for suffix in ("_compressed", "_opt", "_small"):
            b = QPushButton(suffix)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(suffix == suffix_pref)
            b.setFixedHeight(32)
            b.clicked.connect(lambda _c, s=suffix: self._on_suffix(s))
            self._suffix_group.addButton(b)
            row.addWidget(b)
        row.addStretch(1)
        l.addLayout(row)
        return w

    def _build_privacy_info(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)
        for bullet in (
            "No files are ever uploaded to any server.",
            "No telemetry, analytics, or crash reporting.",
            "No internet connection required or used.",
            "Atomic writes prevent corrupting your originals.",
            "Decompression bombs capped at 200 megapixels.",
        ):
            row = QHBoxLayout()
            row.setSpacing(10)
            dot = QLabel("·")
            dot.setStyleSheet("color: #d4956a; font-size: 16px; font-weight: 700;")
            dot.setFixedWidth(12)
            txt = QLabel(bullet)
            txt.setObjectName("muted")
            txt.setWordWrap(True)
            row.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(txt, 1)
            l.addLayout(row)
        return w

    def _on_theme(self, key: str) -> None:
        self._theme = key
        self.theme_changed.emit(key)

    def _on_suffix(self, suffix: str) -> None:
        set_pref("output_suffix", suffix)


# ─────────────────────────────────────────────────────────────────────────────
# About page
# ─────────────────────────────────────────────────────────────────────────────

class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        inner = QWidget()
        il = _page_layout(inner)

        # Header
        il.addWidget(_eyebrow("ABOUT"))
        title = QLabel("Compressly")
        title.setObjectName("h1")
        title.setStyleSheet("font-size: 32px; font-weight: 400; letter-spacing: -1px;")
        il.addWidget(title)
        sub = QLabel(
            "A lightweight, privacy-first desktop image compressor for Windows. "
            "Built with PySide6 and Pillow — no Electron, no Node, no telemetry."
        )
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        il.addWidget(sub)
        il.addWidget(_sep())

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)
        for label, value in (
            ("Formats", "4"),
            ("Presets", "4"),
            ("Uploads", "0"),
            ("License", "MIT"),
        ):
            tile = QWidget()
            tl = QVBoxLayout(tile)
            tl.setContentsMargins(0, 8, 0, 8)
            tl.setSpacing(2)
            v = QLabel(value)
            v.setStyleSheet("font-size: 28px; font-weight: 400; color: #d4956a;")
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel(label)
            lbl.setObjectName("dim")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tl.addWidget(v)
            tl.addWidget(lbl)
            stats_row.addWidget(tile, 1)
        il.addLayout(stats_row)
        il.addWidget(_sep())

        # Feature grid
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)
        features = [
            ("Local & instant",  "All encoding runs on your machine. No uploads, no waiting."),
            ("Modern formats",   "Read JPG, PNG, WebP, BMP, GIF, TIFF. Write JPG, PNG, WebP."),
            ("Smart presets",    "Four hand-tuned recipes for typical workflows."),
            ("Privacy-first",    "No telemetry. No internet. No background processes."),
            ("Lightweight",      "Only two runtime deps: PySide6 + Pillow."),
            ("Multi-threaded",   "Batches compress in parallel without blocking the UI."),
        ]
        for i, (head, body) in enumerate(features):
            card = _surface()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(4)
            h = QLabel(head)
            h.setObjectName("h3")
            b = QLabel(body)
            b.setObjectName("muted")
            b.setWordWrap(True)
            cl.addWidget(h)
            cl.addWidget(b)
            grid.addWidget(card, i // 3, i % 3)
        il.addWidget(grid_w)
        il.addStretch(1)

        outer.addWidget(_scrollable(inner), 1)
