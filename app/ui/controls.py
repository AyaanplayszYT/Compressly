"""Settings & presets panel (right column)."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..models import CompressionSettings, OutputFormat, Preset, ResizeMode
from ..presets import PRESETS

_FORMATS = (OutputFormat.WEBP, OutputFormat.JPEG, OutputFormat.PNG, OutputFormat.KEEP)


def _eyebrow(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("eyebrow")
    return lbl


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(
        "background-color: rgba(128,128,128,0.12); border: none;"
    )
    return f


class ControlsPanel(QWidget):
    """Scrollable settings panel."""

    settings_changed = Signal(object)

    def __init__(
        self, settings: CompressionSettings, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("surface")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._s = settings
        self._block = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(16)

        # Header
        hdr = QVBoxLayout()
        hdr.setSpacing(2)
        hdr.addWidget(_eyebrow("SETTINGS"))
        title = QLabel("Optimization")
        title.setObjectName("h3")
        hdr.addWidget(title)
        root.addLayout(hdr)
        root.addWidget(_divider())

        # ── Format ──────────────────────────────────────────────────────────
        root.addWidget(_eyebrow("OUTPUT FORMAT"))
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(6)
        self._fmt_group = QButtonGroup(self)
        self._fmt_group.setExclusive(True)
        self._fmt_btns: dict[OutputFormat, QPushButton] = {}
        for f in _FORMATS:
            b = QPushButton(f.display)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setMinimumHeight(34)
            b.clicked.connect(lambda _c, fmt=f: self._on_fmt(fmt))
            self._fmt_group.addButton(b)
            self._fmt_btns[f] = b
            fmt_row.addWidget(b, 1)
        root.addLayout(fmt_row)
        root.addWidget(_divider())

        # ── Quality ─────────────────────────────────────────────────────────
        q_head = QHBoxLayout()
        q_head.addWidget(_eyebrow("QUALITY"))
        q_head.addStretch(1)
        self._q_val = QLabel(str(self._s.quality))
        self._q_val.setStyleSheet("font-weight: 700; font-size: 13px;")
        q_head.addWidget(self._q_val)
        root.addLayout(q_head)

        self._q_slider = QSlider(Qt.Orientation.Horizontal)
        self._q_slider.setRange(1, 100)
        self._q_slider.setValue(self._s.quality)
        self._q_slider.valueChanged.connect(self._on_quality)
        root.addWidget(self._q_slider)

        q_legend = QHBoxLayout()
        for txt, align in (
            ("Smallest", Qt.AlignmentFlag.AlignLeft),
            ("Balanced", Qt.AlignmentFlag.AlignCenter),
            ("Best", Qt.AlignmentFlag.AlignRight),
        ):
            lbl = QLabel(txt)
            lbl.setObjectName("dim")
            lbl.setStyleSheet("font-size: 10px;")
            lbl.setAlignment(align)
            q_legend.addWidget(lbl, 1)
        root.addLayout(q_legend)
        root.addWidget(_divider())

        # ── Resize ──────────────────────────────────────────────────────────
        root.addWidget(_eyebrow("RESIZE"))
        resize_row = QHBoxLayout()
        resize_row.setSpacing(6)
        self._resize_group = QButtonGroup(self)
        self._resize_group.setExclusive(True)
        self._resize_btns: dict[ResizeMode, QPushButton] = {}
        for mode, label in (
            (ResizeMode.NONE, "Original"),
            (ResizeMode.PERCENT, "Percent"),
            (ResizeMode.LONGEST, "Max side"),
        ):
            b = QPushButton(label)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setMinimumHeight(34)
            b.clicked.connect(lambda _c, m=mode: self._on_resize_mode(m))
            self._resize_group.addButton(b)
            self._resize_btns[mode] = b
            resize_row.addWidget(b, 1)
        root.addLayout(resize_row)

        self._resize_stack = QStackedWidget()
        self._resize_stack.addWidget(self._page_none())
        self._resize_stack.addWidget(self._page_percent())
        self._resize_stack.addWidget(self._page_longest())
        root.addWidget(self._resize_stack)
        root.addWidget(_divider())

        # ── Options ─────────────────────────────────────────────────────────
        root.addWidget(_eyebrow("OPTIONS"))
        self._strip = QCheckBox("Strip metadata (EXIF, GPS)")
        self._strip.setChecked(self._s.strip_metadata)
        self._strip.toggled.connect(self._on_strip)
        self._aspect = QCheckBox("Preserve aspect ratio")
        self._aspect.setChecked(self._s.keep_aspect_ratio)
        self._aspect.toggled.connect(self._on_aspect)
        root.addWidget(self._strip)
        root.addWidget(self._aspect)
        root.addWidget(_divider())

        # ── Presets ─────────────────────────────────────────────────────────
        root.addWidget(_eyebrow("QUICK PRESETS"))
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, preset in enumerate(PRESETS):
            btn = QPushButton(preset.name)
            btn.setObjectName("chip")
            btn.setMinimumHeight(40)
            btn.setToolTip(preset.description)
            btn.clicked.connect(lambda _c, p=preset: self.apply_preset(p))
            grid.addWidget(btn, i // 2, i % 2)
        root.addLayout(grid)
        root.addStretch(1)

        self._sync()

    # ── public ────────────────────────────────────────────────────────────

    @property
    def settings(self) -> CompressionSettings:
        return self._s

    def apply_preset(self, preset: Preset) -> None:
        self._s = preset.apply(self._s)
        self._sync()
        self._emit()

    def set_settings(self, s: CompressionSettings) -> None:
        self._s = s
        self._sync()

    # ── resize pages ──────────────────────────────────────────────────────

    def _page_none(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 4, 0, 0)
        lbl = QLabel("Output keeps original dimensions.")
        lbl.setObjectName("muted")
        lbl.setStyleSheet("font-size: 11px;")
        l.addWidget(lbl)
        return w

    def _page_percent(self) -> QWidget:
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 4, 0, 0)
        l.setSpacing(10)
        self._pct_slider = QSlider(Qt.Orientation.Horizontal)
        self._pct_slider.setRange(10, 100)
        self._pct_slider.setValue(self._s.resize_percent)
        self._pct_slider.valueChanged.connect(self._on_pct)
        self._pct_val = QLabel(f"{self._s.resize_percent}%")
        self._pct_val.setFixedWidth(44)
        self._pct_val.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._pct_val.setStyleSheet("font-weight: 600;")
        l.addWidget(self._pct_slider, 1)
        l.addWidget(self._pct_val)
        return w

    def _page_longest(self) -> QWidget:
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 4, 0, 0)
        l.setSpacing(10)
        lbl = QLabel("Longest side")
        lbl.setObjectName("muted")
        self._longest = QSpinBox()
        self._longest.setRange(64, 16384)
        self._longest.setSuffix(" px")
        self._longest.setValue(self._s.resize_longest)
        self._longest.valueChanged.connect(self._on_longest)
        l.addWidget(lbl, 1)
        l.addWidget(self._longest)
        return w

    # ── handlers ──────────────────────────────────────────────────────────

    def _on_fmt(self, fmt: OutputFormat) -> None:
        if not self._block:
            self._s = replace(self._s, output_format=fmt)
            self._emit()

    def _on_quality(self, v: int) -> None:
        self._q_val.setText(str(v))
        if not self._block:
            self._s = replace(self._s, quality=v)
            self._emit()

    def _on_resize_mode(self, m: ResizeMode) -> None:
        if not self._block:
            self._s = replace(self._s, resize_mode=m)
            self._update_resize_stack()
            self._emit()

    def _on_pct(self, v: int) -> None:
        self._pct_val.setText(f"{v}%")
        if not self._block:
            self._s = replace(self._s, resize_percent=v)
            self._emit()

    def _on_longest(self, v: int) -> None:
        if not self._block:
            self._s = replace(self._s, resize_longest=v)
            self._emit()

    def _on_strip(self, v: bool) -> None:
        if not self._block:
            self._s = replace(self._s, strip_metadata=v)
            self._emit()

    def _on_aspect(self, v: bool) -> None:
        if not self._block:
            self._s = replace(self._s, keep_aspect_ratio=v)
            self._emit()

    # ── sync ──────────────────────────────────────────────────────────────

    def _sync(self) -> None:
        self._block = True
        try:
            for f, b in self._fmt_btns.items():
                b.setChecked(f == self._s.output_format)
            self._q_slider.setValue(self._s.quality)
            self._q_val.setText(str(self._s.quality))
            for m, b in self._resize_btns.items():
                b.setChecked(m == self._s.resize_mode)
            self._update_resize_stack()
            self._pct_slider.setValue(self._s.resize_percent)
            self._pct_val.setText(f"{self._s.resize_percent}%")
            self._longest.setValue(self._s.resize_longest)
            self._strip.setChecked(self._s.strip_metadata)
            self._aspect.setChecked(self._s.keep_aspect_ratio)
        finally:
            self._block = False

    def _update_resize_stack(self) -> None:
        self._resize_stack.setCurrentIndex(
            {
                ResizeMode.NONE: 0,
                ResizeMode.PERCENT: 1,
                ResizeMode.LONGEST: 2,
            }[self._s.resize_mode]
        )

    def _emit(self) -> None:
        self.settings_changed.emit(self._s)
