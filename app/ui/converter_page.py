"""Image Converter page — drop any image, pick format, download.

No compression settings needed. Simple UX for format conversion only.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .helpers import format_bytes


def _surface() -> QFrame:
    f = QFrame()
    f.setObjectName("surface")
    f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return f


def _sep() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet("background-color: rgba(255,255,255,0.07);")
    return w


_FORMATS = [
    ("WebP",  "webp",  "image/webp",  "Best for web — smallest size"),
    ("PNG",   "png",   "image/png",   "Lossless — preserves transparency"),
    ("JPG",   "jpeg",  "image/jpeg",  "Universal — widest compatibility"),
    ("AVIF",  "avif",  "image/avif",  "Next-gen — even smaller than WebP"),
]


class _ConvertSignals(QObject):
    finished = Signal(bytes, str, str)  # data, ext, original_stem
    error    = Signal(str)


class _ConvertWorker(QRunnable):
    def __init__(self, path: Path, fmt_mime: str, fmt_ext: str,
                 signals: _ConvertSignals) -> None:
        super().__init__()
        self._path = path
        self._mime = fmt_mime
        self._ext  = fmt_ext
        self._signals = signals
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            from PIL import Image, ImageOps
            with Image.open(self._path) as img:
                img = ImageOps.exif_transpose(img)
                if self._mime == "image/jpeg" and img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = bg
                buf = io.BytesIO()
                save_fmt = "JPEG" if self._mime == "image/jpeg" else self._ext.upper()
                kw: dict = {}
                if save_fmt == "JPEG":
                    kw = {"quality": 92, "optimize": True}
                elif save_fmt == "WEBP":
                    kw = {"quality": 90, "method": 4}
                img.save(buf, format=save_fmt, **kw)
            self._signals.finished.emit(
                buf.getvalue(), self._ext, self._path.stem
            )
        except Exception as exc:
            self._signals.error.emit(str(exc))


class ConverterPage(QWidget):
    """Standalone image format converter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        self._result_bytes: Optional[bytes] = None
        self._result_ext   = "webp"
        self._result_stem  = "output"
        self._selected_fmt = "webp"
        self._selected_mime = "image/webp"
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(16)

        # Header
        eyebrow = QLabel("IMAGE CONVERTER")
        eyebrow.setObjectName("eyebrow")
        il.addWidget(eyebrow)

        title = QLabel("Convert to any format")
        title.setObjectName("h1")
        il.addWidget(title)

        sub = QLabel(
            "Drop an image, pick the output format, and download. "
            "No quality settings needed — uses sensible defaults."
        )
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        il.addWidget(sub)
        il.addWidget(_sep())

        # Format picker
        fmt_card = _surface()
        fmt_l = QVBoxLayout(fmt_card)
        fmt_l.setContentsMargins(18, 14, 18, 14)
        fmt_l.setSpacing(10)
        fmt_title = QLabel("Output format")
        fmt_title.setObjectName("h3")
        fmt_l.addWidget(fmt_title)

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(8)
        self._fmt_group = QButtonGroup(self)
        self._fmt_group.setExclusive(True)
        self._fmt_btns: dict[str, QPushButton] = {}

        for label, ext, mime, hint in _FORMATS:
            col = QVBoxLayout()
            col.setSpacing(4)
            btn = QPushButton(label)
            btn.setObjectName("chip")
            btn.setCheckable(True)
            btn.setChecked(ext == "webp")
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda _c, e=ext, m=mime: self._on_fmt(e, m))
            self._fmt_group.addButton(btn)
            self._fmt_btns[ext] = btn
            hint_lbl = QLabel(hint)
            hint_lbl.setObjectName("dim")
            hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(btn)
            col.addWidget(hint_lbl)
            fmt_row.addLayout(col, 1)

        fmt_l.addLayout(fmt_row)
        il.addWidget(fmt_card)

        # Drop zone
        self._drop = _ConvDropZone()
        self._drop.file_dropped.connect(self._on_file)
        il.addWidget(self._drop)

        # Status
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

        # Result card
        result_card = _surface()
        result_l = QHBoxLayout(result_card)
        result_l.setContentsMargins(18, 14, 18, 14)
        result_l.setSpacing(12)

        self._result_info = QLabel("No conversion yet")
        self._result_info.setObjectName("muted")
        result_l.addWidget(self._result_info, 1)

        self._save_btn = QPushButton("Download")
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.setFixedHeight(34)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        result_l.addWidget(self._save_btn)

        il.addWidget(result_card)
        il.addStretch(1)

        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(inner)
        outer.addWidget(sa, 1)

    # ── drag & drop ───────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"):
                self._on_file(path)
                break

    # ── internal ──────────────────────────────────────────────────────────

    def _on_fmt(self, ext: str, mime: str) -> None:
        self._selected_fmt  = ext
        self._selected_mime = mime

    def _on_file(self, path: Path) -> None:
        self._result_bytes = None
        self._save_btn.setEnabled(False)
        self._status.setText(f"Converting to {self._selected_fmt.upper()}…")
        self._status.setVisible(True)
        self._progress.setVisible(True)

        signals = _ConvertSignals()
        signals.finished.connect(self._on_done)
        signals.error.connect(self._on_error)

        worker = _ConvertWorker(path, self._selected_mime,
                                self._selected_fmt, signals)
        self._pool.start(worker)

    def _on_done(self, data: bytes, ext: str, stem: str) -> None:
        self._result_bytes = data
        self._result_ext   = ext
        self._result_stem  = stem
        self._progress.setVisible(False)
        self._status.setVisible(False)
        self._result_info.setText(
            f"{stem}.{ext}  ·  {format_bytes(len(data))}"
        )
        self._save_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._status.setText(f"Error: {msg}")
        self._status.setStyleSheet("color: #c0675a;")

    def _on_save(self) -> None:
        if not self._result_bytes:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save converted image",
            str(Path.home() / f"{self._result_stem}.{self._result_ext}"),
            f"{self._result_ext.upper()} Image (*.{self._result_ext})",
        )
        if dest:
            Path(dest).write_bytes(self._result_bytes)


class _ConvDropZone(QFrame):
    file_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setFixedHeight(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setSpacing(6)

        icon = QLabel("⇄")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("color: #d4956a; font-size: 24px;")
        l.addWidget(icon)

        title = QLabel("Drop an image to convert")
        title.setObjectName("h3")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(title)

        sub = QLabel("or click to browse")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(sub)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select image", str(Path.home()),
                "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff)",
            )
            if files:
                self.file_dropped.emit(Path(files[0]))
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("hover", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"):
                event.acceptProposedAction()
                self.file_dropped.emit(path)
                return
