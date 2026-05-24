"""Feature pages: Resizer, Watermark, EXIF Viewer, GIF Optimiser, PDF Tools.

All pages follow the same pattern:
  - Drop zone at the top
  - Controls in the middle
  - Result preview + save button at the bottom
  - Background worker thread so UI never freezes
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from .helpers import format_bytes


# ── Shared helpers ────────────────────────────────────────────────────────────

def _surface() -> QFrame:
    f = QFrame()
    f.setObjectName("surface")
    f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return f


def _sep() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet("background-color: rgba(128,128,128,0.15);")
    return w


def _eyebrow(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("eyebrow")
    return l


def _h1(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("h1")
    return l


def _h3(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("h3")
    return l


def _muted(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("muted")
    l.setWordWrap(True)
    return l


class _Signals(QObject):
    finished = Signal(bytes, str, str)  # data, ext, stem
    error    = Signal(str)
    progress = Signal(str)


class _DropZone(QFrame):
    file_dropped = Signal(object)

    def __init__(self, icon: str = "⤓", title: str = "Drop an image here",
                 sub: str = "or click to browse  ·  JPG · PNG · WebP · BMP",
                 multi: bool = False) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setFixedHeight(100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._multi = multi
        l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setSpacing(5)
        ic = QLabel(icon)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("color: #d4956a; font-size: 20px;")
        l.addWidget(ic)
        t = QLabel(title)
        t.setObjectName("h3")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(t)
        s = QLabel(sub)
        s.setObjectName("muted")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(s)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._multi:
                files, _ = QFileDialog.getOpenFileNames(
                    self, "Select images", str(Path.home()),
                    "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff)")
                for f in files:
                    self.file_dropped.emit(Path(f))
            else:
                files, _ = QFileDialog.getOpenFileNames(
                    self, "Select file", str(Path.home()),
                    "Images & PDFs (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff *.pdf)")
                if files:
                    self.file_dropped.emit(Path(files[0]))
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("hover", True)
            self.style().unpolish(self); self.style().polish(self)

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("hover", False)
        self.style().unpolish(self); self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("hover", False)
        self.style().unpolish(self); self.style().polish(self)
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            self.file_dropped.emit(path)
            if not self._multi:
                break
        event.acceptProposedAction()


def _page_wrap(inner: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(inner)
    return sa


# ── Image Resizer ─────────────────────────────────────────────────────────────

class _ResizeWorker(QRunnable):
    def __init__(self, path: Path, w: int, h: int, mode: str,
                 fmt: str, signals: _Signals) -> None:
        super().__init__()
        self._path = path
        self._w = w; self._h = h; self._mode = mode
        self._fmt = fmt; self._signals = signals
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            from PIL import Image, ImageOps
            with Image.open(self._path) as img:
                img = ImageOps.exif_transpose(img)
                ow, oh = img.size
                if self._mode == "pixels":
                    nw = self._w or int(ow * self._h / oh)
                    nh = self._h or int(oh * self._w / ow)
                elif self._mode == "percent":
                    nw = int(ow * self._w / 100)
                    nh = int(oh * self._w / 100)
                else:  # longest
                    scale = self._w / max(ow, oh)
                    nw, nh = int(ow * scale), int(oh * scale)
                resized = img.resize((max(1, nw), max(1, nh)), Image.Resampling.LANCZOS)
                if self._fmt == "jpeg" and resized.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", resized.size, (255, 255, 255))
                    bg.paste(resized, mask=resized.split()[-1] if resized.mode in ("RGBA","LA") else None)
                    resized = bg
                buf = io.BytesIO()
                resized.save(buf, format=self._fmt.upper(), quality=92, optimize=True)
                ext = {"jpeg": "jpg"}.get(self._fmt, self._fmt)
                self._signals.finished.emit(buf.getvalue(), ext, self._path.stem)
        except Exception as exc:
            self._signals.error.emit(str(exc))


class ResizerPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self); self._pool.setMaxThreadCount(2)
        self._signals: Optional[_Signals] = None
        self._result: Optional[bytes] = None
        self._result_ext = "jpg"
        self._result_stem = "output"
        self._current_path: Optional[Path] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("IMAGE RESIZER"))
        il.addWidget(_h1("Resize without compressing"))
        il.addWidget(_muted("Resize by pixels, percentage, or longest side. Output quality is always maximum."))
        il.addWidget(_sep())

        drop = _DropZone("⤢", "Drop an image to resize")
        drop.file_dropped.connect(self._on_file)
        il.addWidget(drop)

        # Controls
        ctrl = _surface()
        cl = QVBoxLayout(ctrl)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        # Mode
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._mode_grp = QButtonGroup(self)
        self._mode_grp.setExclusive(True)
        self._mode_btns: dict[str, QPushButton] = {}
        for key, lbl in (("pixels", "Pixels"), ("percent", "Percent"), ("longest", "Longest side")):
            b = QPushButton(lbl)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(key == "pixels")
            b.clicked.connect(lambda _c, k=key: self._set_mode(k))
            self._mode_grp.addButton(b)
            self._mode_btns[key] = b
            mode_row.addWidget(b, 1)
        cl.addLayout(mode_row)

        # Value inputs
        val_row = QHBoxLayout()
        val_row.setSpacing(10)
        self._w_spin = QSpinBox()
        self._w_spin.setRange(1, 16000)
        self._w_spin.setValue(1920)
        self._w_spin.setSuffix(" px")
        self._h_spin = QSpinBox()
        self._h_spin.setRange(1, 16000)
        self._h_spin.setValue(1080)
        self._h_spin.setSuffix(" px")
        self._pct_spin = QSpinBox()
        self._pct_spin.setRange(1, 400)
        self._pct_spin.setValue(50)
        self._pct_spin.setSuffix(" %")
        self._pct_spin.setVisible(False)
        self._lock_check = QCheckBox("Lock aspect ratio")
        self._lock_check.setChecked(True)
        val_row.addWidget(QLabel("W"))
        val_row.addWidget(self._w_spin, 1)
        val_row.addWidget(QLabel("H"))
        val_row.addWidget(self._h_spin, 1)
        val_row.addWidget(self._pct_spin, 1)
        val_row.addWidget(self._lock_check)
        cl.addLayout(val_row)

        # Format
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(8)
        fmt_row.addWidget(_h3("Output format"))
        self._fmt_combo = QComboBox()
        for f in ("WebP", "JPG", "PNG"):
            self._fmt_combo.addItem(f, f.lower().replace("jpg", "jpeg"))
        fmt_row.addWidget(self._fmt_combo)
        fmt_row.addStretch(1)
        cl.addLayout(fmt_row)

        self._resize_btn = QPushButton("Resize")
        self._resize_btn.setProperty("variant", "primary")
        self._resize_btn.setFixedHeight(34)
        self._resize_btn.setEnabled(False)
        self._resize_btn.clicked.connect(self._run)
        cl.addWidget(self._resize_btn)
        il.addWidget(ctrl)

        self._status = QLabel("")
        self._status.setObjectName("muted")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setVisible(False)
        il.addWidget(self._status)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        il.addWidget(self._progress)

        result_row = QHBoxLayout()
        self._result_lbl = QLabel("No result yet")
        self._result_lbl.setObjectName("muted")
        result_row.addWidget(self._result_lbl, 1)
        self._save_btn = QPushButton("Save")
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.setFixedHeight(32)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        result_row.addWidget(self._save_btn)
        il.addLayout(result_row)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)

    def _set_mode(self, mode: str) -> None:
        self._w_spin.setVisible(mode != "percent")
        self._h_spin.setVisible(mode == "pixels")
        self._pct_spin.setVisible(mode == "percent")
        self._lock_check.setVisible(mode == "pixels")

    def _on_file(self, path: Path) -> None:
        self._current_path = path
        self._resize_btn.setEnabled(True)
        self._status.setText(f"Loaded: {path.name}")
        self._status.setVisible(True)

    def _run(self) -> None:
        if not self._current_path:
            return
        mode = next(k for k, b in self._mode_btns.items() if b.isChecked())
        w = self._pct_spin.value() if mode == "percent" else self._w_spin.value()
        h = self._h_spin.value() if mode == "pixels" else 0
        fmt = self._fmt_combo.currentData()
        self._result = None
        self._save_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._signals = _Signals()
        self._signals.finished.connect(self._on_done)
        self._signals.error.connect(self._on_error)
        self._pool.start(_ResizeWorker(self._current_path, w, h, mode, fmt, self._signals))

    def _on_done(self, data: bytes, ext: str, stem: str) -> None:
        self._result = data; self._result_ext = ext; self._result_stem = stem
        self._progress.setVisible(False)
        self._result_lbl.setText(f"{stem}.{ext}  ·  {format_bytes(len(data))}")
        self._save_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._status.setText(f"Error: {msg}")
        self._status.setStyleSheet("color: #d07060;")

    def _save(self) -> None:
        if not self._result:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save resized image",
            str(Path.home() / f"{self._result_stem}_resized.{self._result_ext}"),
            f"{self._result_ext.upper()} (*.{self._result_ext})")
        if dest:
            Path(dest).write_bytes(self._result)


# ── Watermark Tool ────────────────────────────────────────────────────────────

class _WatermarkWorker(QRunnable):
    def __init__(self, path: Path, text: str, opacity: int, size: int,
                 position: str, color: str, signals: _Signals) -> None:
        super().__init__()
        self._path = path; self._text = text; self._opacity = opacity
        self._size = size; self._position = position; self._color = color
        self._signals = signals; self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageOps
            with Image.open(self._path) as img:
                img = ImageOps.exif_transpose(img).convert("RGBA")
            w, h = img.size
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            try:
                font = ImageFont.truetype("arialbd.ttf", self._size)
            except OSError:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), self._text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = int(min(w, h) * 0.04)
            positions = {
                "top-left":     (pad, pad),
                "top-center":   ((w - tw) // 2, pad),
                "top-right":    (w - tw - pad, pad),
                "center-left":  (pad, (h - th) // 2),
                "center":       ((w - tw) // 2, (h - th) // 2),
                "center-right": (w - tw - pad, (h - th) // 2),
                "bottom-left":  (pad, h - th - pad),
                "bottom-center":((w - tw) // 2, h - th - pad),
                "bottom-right": (w - tw - pad, h - th - pad),
            }
            x, y = positions.get(self._position, positions["bottom-right"])
            r, g, b = int(self._color[1:3], 16), int(self._color[3:5], 16), int(self._color[5:7], 16)
            draw.text((x, y), self._text, font=font, fill=(r, g, b, self._opacity))
            result = Image.alpha_composite(img, overlay)
            buf = io.BytesIO()
            result.save(buf, format="PNG")
            self._signals.finished.emit(buf.getvalue(), "png", self._path.stem)
        except Exception as exc:
            self._signals.error.emit(str(exc))


class WatermarkPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self); self._pool.setMaxThreadCount(2)
        self._signals: Optional[_Signals] = None
        self._result: Optional[bytes] = None
        self._current_path: Optional[Path] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("WATERMARK TOOL"))
        il.addWidget(_h1("Add text watermarks"))
        il.addWidget(_muted("Add a text overlay to your images before saving. Supports opacity, size, position, and colour."))
        il.addWidget(_sep())

        drop = _DropZone("⊕", "Drop an image to watermark")
        drop.file_dropped.connect(self._on_file)
        il.addWidget(drop)

        ctrl = _surface()
        cl = QVBoxLayout(ctrl)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        # Text
        text_row = QHBoxLayout()
        text_row.addWidget(_h3("Text"))
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("© 2026 Your Name")
        text_row.addWidget(self._text_input, 1)
        cl.addLayout(text_row)

        # Size + opacity
        so_row = QHBoxLayout()
        so_row.setSpacing(16)
        so_row.addWidget(QLabel("Size"))
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(10, 200)
        self._size_slider.setValue(40)
        so_row.addWidget(self._size_slider, 1)
        so_row.addWidget(QLabel("Opacity"))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(10, 255)
        self._opacity_slider.setValue(180)
        so_row.addWidget(self._opacity_slider, 1)
        cl.addLayout(so_row)

        # Position grid
        cl.addWidget(_h3("Position"))
        grid = QGridLayout()
        grid.setSpacing(4)
        self._pos_grp = QButtonGroup(self)
        self._pos_grp.setExclusive(True)
        positions = [
            ("top-left","↖"), ("top-center","↑"), ("top-right","↗"),
            ("center-left","←"), ("center","·"), ("center-right","→"),
            ("bottom-left","↙"), ("bottom-center","↓"), ("bottom-right","↘"),
        ]
        for i, (key, sym) in enumerate(positions):
            b = QPushButton(sym)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(key == "bottom-right")
            b.setFixedSize(36, 36)
            self._pos_grp.addButton(b)
            b.setProperty("posKey", key)
            grid.addWidget(b, i // 3, i % 3)
        cl.addLayout(grid)

        # Colour
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Colour"))
        self._color_combo = QComboBox()
        for name, val in (("White", "#ffffff"), ("Black", "#000000"),
                          ("Terracotta", "#d4956a"), ("Red", "#e05050"),
                          ("Yellow", "#f0c040")):
            self._color_combo.addItem(name, val)
        color_row.addWidget(self._color_combo)
        color_row.addStretch(1)
        cl.addLayout(color_row)

        self._wm_btn = QPushButton("Apply watermark")
        self._wm_btn.setProperty("variant", "primary")
        self._wm_btn.setFixedHeight(34)
        self._wm_btn.setEnabled(False)
        self._wm_btn.clicked.connect(self._run)
        cl.addWidget(self._wm_btn)
        il.addWidget(ctrl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        il.addWidget(self._progress)

        result_row = QHBoxLayout()
        self._result_lbl = QLabel("No result yet")
        self._result_lbl.setObjectName("muted")
        result_row.addWidget(self._result_lbl, 1)
        self._save_btn = QPushButton("Save")
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.setFixedHeight(32)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        result_row.addWidget(self._save_btn)
        il.addLayout(result_row)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)

    def _on_file(self, path: Path) -> None:
        self._current_path = path
        self._wm_btn.setEnabled(True)

    def _run(self) -> None:
        if not self._current_path:
            return
        text = self._text_input.text() or "Watermark"
        pos_btn = self._pos_grp.checkedButton()
        pos = pos_btn.property("posKey") if pos_btn else "bottom-right"
        self._result = None
        self._save_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._signals = _Signals()
        self._signals.finished.connect(self._on_done)
        self._signals.error.connect(self._on_error)
        self._pool.start(_WatermarkWorker(
            self._current_path, text,
            self._opacity_slider.value(), self._size_slider.value(),
            pos, self._color_combo.currentData(), self._signals))

    def _on_done(self, data: bytes, ext: str, stem: str) -> None:
        self._result = data
        self._progress.setVisible(False)
        self._result_lbl.setText(f"{stem}_watermarked.{ext}  ·  {format_bytes(len(data))}")
        self._save_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._result_lbl.setText(f"Error: {msg}")
        self._result_lbl.setStyleSheet("color: #d07060;")

    def _save(self) -> None:
        if not self._result:
            return
        stem = self._current_path.stem if self._current_path else "output"
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save watermarked image",
            str(Path.home() / f"{stem}_watermarked.png"), "PNG (*.png)")
        if dest:
            Path(dest).write_bytes(self._result)


# ── EXIF Viewer ───────────────────────────────────────────────────────────────

class ExifPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_path: Optional[Path] = None
        self._exif_data: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("EXIF VIEWER"))
        il.addWidget(_h1("View & strip metadata"))
        il.addWidget(_muted("See camera model, GPS, date, lens, and more. Strip all or selected fields."))
        il.addWidget(_sep())

        drop = _DropZone("⊞", "Drop an image to inspect")
        drop.file_dropped.connect(self._on_file)
        il.addWidget(drop)

        # EXIF table
        self._exif_card = _surface()
        self._exif_card.setVisible(False)
        ec = QVBoxLayout(self._exif_card)
        ec.setContentsMargins(16, 14, 16, 14)
        ec.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.addWidget(_h3("Metadata"), 1)
        self._strip_all_btn = QPushButton("Strip all & save")
        self._strip_all_btn.setProperty("variant", "danger")
        self._strip_all_btn.setFixedHeight(30)
        self._strip_all_btn.clicked.connect(self._strip_all)
        hdr.addWidget(self._strip_all_btn)
        ec.addLayout(hdr)

        self._exif_grid = QGridLayout()
        self._exif_grid.setSpacing(4)
        self._exif_grid.setColumnStretch(1, 1)
        ec.addLayout(self._exif_grid)
        il.addWidget(self._exif_card)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)

    def _on_file(self, path: Path) -> None:
        self._current_path = path
        self._load_exif(path)

    def _load_exif(self, path: Path) -> None:
        # Clear old grid
        while self._exif_grid.count():
            item = self._exif_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            with Image.open(path) as img:
                raw = img._getexif() or {}
                self._exif_data = {TAGS.get(k, str(k)): str(v)[:120]
                                   for k, v in raw.items()}
        except Exception:
            self._exif_data = {}

        if not self._exif_data:
            lbl = QLabel("No EXIF data found in this image.")
            lbl.setObjectName("muted")
            self._exif_grid.addWidget(lbl, 0, 0, 1, 2)
        else:
            for row, (key, val) in enumerate(sorted(self._exif_data.items())):
                k_lbl = QLabel(key)
                k_lbl.setObjectName("dim")
                k_lbl.setFixedWidth(160)
                v_lbl = QLabel(val)
                v_lbl.setObjectName("muted")
                v_lbl.setWordWrap(True)
                self._exif_grid.addWidget(k_lbl, row, 0)
                self._exif_grid.addWidget(v_lbl, row, 1)

        self._exif_card.setVisible(True)

    def _strip_all(self) -> None:
        if not self._current_path:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save without metadata",
            str(Path.home() / f"{self._current_path.stem}_clean{self._current_path.suffix}"),
            "Images (*.jpg *.jpeg *.png *.webp)")
        if not dest:
            return
        try:
            from PIL import Image, ImageOps
            with Image.open(self._current_path) as img:
                img = ImageOps.exif_transpose(img)
                clean = img.copy()
            clean.save(dest)
        except Exception:
            pass


# ── GIF Optimiser ─────────────────────────────────────────────────────────────

class _GifWorker(QRunnable):
    def __init__(self, path: Path, skip: int, colors: int, signals: _Signals) -> None:
        super().__init__()
        self._path = path; self._skip = skip; self._colors = colors
        self._signals = signals; self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            from PIL import Image
            self._signals.progress.emit("Loading GIF frames…")
            with Image.open(self._path) as gif:
                frames = []
                durations = []
                try:
                    while True:
                        frames.append(gif.copy().convert("RGBA"))
                        durations.append(gif.info.get("duration", 100))
                        gif.seek(gif.tell() + 1)
                except EOFError:
                    pass

            self._signals.progress.emit(f"Optimising {len(frames)} frames…")
            kept = frames[::max(1, self._skip + 1)]
            kept_dur = durations[::max(1, self._skip + 1)]

            # Quantize each frame
            quantized = []
            for f in kept:
                q = f.convert("P", palette=Image.Palette.ADAPTIVE, colors=self._colors)
                quantized.append(q)

            buf = io.BytesIO()
            quantized[0].save(
                buf, format="GIF", save_all=True,
                append_images=quantized[1:],
                duration=kept_dur, loop=0, optimize=True)
            self._signals.finished.emit(buf.getvalue(), "gif", self._path.stem)
        except Exception as exc:
            self._signals.error.emit(str(exc))


class GifPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self); self._pool.setMaxThreadCount(1)
        self._signals: Optional[_Signals] = None
        self._result: Optional[bytes] = None
        self._current_path: Optional[Path] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("GIF OPTIMISER"))
        il.addWidget(_h1("Reduce GIF file size"))
        il.addWidget(_muted("Drop a GIF to reduce its size by skipping frames and reducing the colour palette."))
        il.addWidget(_sep())

        drop = _DropZone("⊛", "Drop a GIF file", "or click to browse  ·  GIF only")
        drop.file_dropped.connect(self._on_file)
        il.addWidget(drop)

        ctrl = _surface()
        cl = QVBoxLayout(ctrl)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        skip_row = QHBoxLayout()
        skip_row.addWidget(_h3("Skip every N frames"))
        self._skip_spin = QSpinBox()
        self._skip_spin.setRange(0, 10)
        self._skip_spin.setValue(1)
        self._skip_spin.setToolTip("0 = keep all frames, 1 = keep every other frame")
        skip_row.addWidget(self._skip_spin)
        skip_row.addStretch(1)
        cl.addLayout(skip_row)

        colors_row = QHBoxLayout()
        colors_row.addWidget(_h3("Colour palette size"))
        self._colors_spin = QSpinBox()
        self._colors_spin.setRange(8, 256)
        self._colors_spin.setValue(128)
        colors_row.addWidget(self._colors_spin)
        colors_row.addStretch(1)
        cl.addLayout(colors_row)

        self._opt_btn = QPushButton("Optimise GIF")
        self._opt_btn.setProperty("variant", "primary")
        self._opt_btn.setFixedHeight(34)
        self._opt_btn.setEnabled(False)
        self._opt_btn.clicked.connect(self._run)
        cl.addWidget(self._opt_btn)
        il.addWidget(ctrl)

        self._status = QLabel("")
        self._status.setObjectName("muted")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setVisible(False)
        il.addWidget(self._status)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        il.addWidget(self._progress)

        result_row = QHBoxLayout()
        self._result_lbl = QLabel("No result yet")
        self._result_lbl.setObjectName("muted")
        result_row.addWidget(self._result_lbl, 1)
        self._save_btn = QPushButton("Save")
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.setFixedHeight(32)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        result_row.addWidget(self._save_btn)
        il.addLayout(result_row)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)

    def _on_file(self, path: Path) -> None:
        if path.suffix.lower() != ".gif":
            return
        self._current_path = path
        self._opt_btn.setEnabled(True)
        self._status.setText(f"Loaded: {path.name}  ({format_bytes(path.stat().st_size)})")
        self._status.setVisible(True)

    def _run(self) -> None:
        if not self._current_path:
            return
        self._result = None
        self._save_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._signals = _Signals()
        self._signals.progress.connect(lambda m: self._status.setText(m))
        self._signals.finished.connect(self._on_done)
        self._signals.error.connect(self._on_error)
        self._pool.start(_GifWorker(
            self._current_path, self._skip_spin.value(),
            self._colors_spin.value(), self._signals))

    def _on_done(self, data: bytes, ext: str, stem: str) -> None:
        self._result = data
        self._progress.setVisible(False)
        orig = self._current_path.stat().st_size if self._current_path else 0
        pct = (1 - len(data) / orig) * 100 if orig else 0
        self._result_lbl.setText(
            f"{stem}_opt.gif  ·  {format_bytes(len(data))}  (−{pct:.0f}%)")
        self._save_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._result_lbl.setText(f"Error: {msg}")

    def _save(self) -> None:
        if not self._result:
            return
        stem = self._current_path.stem if self._current_path else "output"
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save optimised GIF",
            str(Path.home() / f"{stem}_opt.gif"), "GIF (*.gif)")
        if dest:
            Path(dest).write_bytes(self._result)


# ── PDF Tools ─────────────────────────────────────────────────────────────────

class _PdfWorker(QRunnable):
    def __init__(self, path: Path, fmt: str, quality: int, signals: _Signals) -> None:
        super().__init__()
        self._path = path; self._fmt = fmt; self._quality = quality
        self._signals = signals; self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            import pypdfium2 as pdfium
            from PIL import Image
            self._signals.progress.emit("Opening PDF…")
            pdf = pdfium.PdfDocument(str(self._path))
            pages = len(pdf)
            self._signals.progress.emit(f"Rendering {pages} pages…")
            results = []
            for i in range(pages):
                page = pdf[i]
                bitmap = page.render(scale=2.0)
                pil_img = bitmap.to_pil()
                if self._fmt == "jpeg" and pil_img.mode in ("RGBA", "LA"):
                    bg = Image.new("RGB", pil_img.size, (255, 255, 255))
                    bg.paste(pil_img, mask=pil_img.split()[-1])
                    pil_img = bg
                buf = io.BytesIO()
                pil_img.save(buf, format=self._fmt.upper(), quality=self._quality, optimize=True)
                results.append(buf.getvalue())
            # Pack all pages into a zip
            import zipfile as zf
            zbuf = io.BytesIO()
            ext = {"jpeg": "jpg"}.get(self._fmt, self._fmt)
            with zf.ZipFile(zbuf, "w", zf.ZIP_DEFLATED) as z:
                for i, data in enumerate(results):
                    z.writestr(f"page_{i+1:03d}.{ext}", data)
            self._signals.finished.emit(zbuf.getvalue(), "zip", self._path.stem)
        except ImportError:
            self._signals.error.emit(
                "pypdfium2 not installed. Run: pip install pypdfium2")
        except Exception as exc:
            self._signals.error.emit(str(exc))


class PdfPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self); self._pool.setMaxThreadCount(1)
        self._signals: Optional[_Signals] = None
        self._result: Optional[bytes] = None
        self._current_path: Optional[Path] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("PDF TOOLS"))
        il.addWidget(_h1("PDF → Images"))
        il.addWidget(_muted("Extract every page from a PDF as a high-quality image. All pages are saved in a ZIP archive."))
        il.addWidget(_sep())

        drop = _DropZone("⊟", "Drop a PDF file", "or click to browse  ·  PDF only")
        drop.file_dropped.connect(self._on_file)
        il.addWidget(drop)

        ctrl = _surface()
        cl = QVBoxLayout(ctrl)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(_h3("Output format"))
        self._fmt_combo = QComboBox()
        for f in ("WebP", "JPG", "PNG"):
            self._fmt_combo.addItem(f, f.lower().replace("jpg", "jpeg"))
        fmt_row.addWidget(self._fmt_combo)
        fmt_row.addStretch(1)
        cl.addLayout(fmt_row)

        q_row = QHBoxLayout()
        q_row.addWidget(QLabel("Quality"))
        self._q_slider = QSlider(Qt.Orientation.Horizontal)
        self._q_slider.setRange(50, 100)
        self._q_slider.setValue(90)
        q_row.addWidget(self._q_slider, 1)
        cl.addLayout(q_row)

        self._extract_btn = QPushButton("Extract pages")
        self._extract_btn.setProperty("variant", "primary")
        self._extract_btn.setFixedHeight(34)
        self._extract_btn.setEnabled(False)
        self._extract_btn.clicked.connect(self._run)
        cl.addWidget(self._extract_btn)
        il.addWidget(ctrl)

        self._status = QLabel("")
        self._status.setObjectName("muted")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setVisible(False)
        il.addWidget(self._status)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        il.addWidget(self._progress)

        result_row = QHBoxLayout()
        self._result_lbl = QLabel("No result yet")
        self._result_lbl.setObjectName("muted")
        result_row.addWidget(self._result_lbl, 1)
        self._save_btn = QPushButton("Save ZIP")
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.setFixedHeight(32)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        result_row.addWidget(self._save_btn)
        il.addLayout(result_row)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)

    def _on_file(self, path: Path) -> None:
        if path.suffix.lower() != ".pdf":
            return
        self._current_path = path
        self._extract_btn.setEnabled(True)
        self._status.setText(f"Loaded: {path.name}")
        self._status.setVisible(True)

    def _run(self) -> None:
        if not self._current_path:
            return
        self._result = None
        self._save_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._signals = _Signals()
        self._signals.progress.connect(lambda m: self._status.setText(m))
        self._signals.finished.connect(self._on_done)
        self._signals.error.connect(self._on_error)
        self._pool.start(_PdfWorker(
            self._current_path, self._fmt_combo.currentData(),
            self._q_slider.value(), self._signals))

    def _on_done(self, data: bytes, ext: str, stem: str) -> None:
        self._result = data
        self._progress.setVisible(False)
        self._result_lbl.setText(f"{stem}_pages.zip  ·  {format_bytes(len(data))}")
        self._save_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._status.setText(f"Error: {msg}")
        self._status.setStyleSheet("color: #d07060;")

    def _save(self) -> None:
        if not self._result:
            return
        stem = self._current_path.stem if self._current_path else "output"
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save pages as ZIP",
            str(Path.home() / f"{stem}_pages.zip"), "ZIP (*.zip)")
        if dest:
            Path(dest).write_bytes(self._result)
