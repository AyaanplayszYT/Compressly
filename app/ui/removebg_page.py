"""Background Remover page — native Pillow + manual brush refinement.

Two modes:
  Auto:     Colour-distance algorithm removes the background automatically.
  Advanced: After auto-removal, user can paint keep/remove strokes to refine.

No external model downloads. No internet required.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QObject, QPoint, QRect, QRunnable, QSize, QThreadPool, Qt, Signal, Slot,
)
from PySide6.QtGui import (
    QColor, QCursor, QDragEnterEvent, QDropEvent,
    QImage, QPainter, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QScrollArea, QSlider,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..engine.bg_remove import remove_background
from .helpers import format_bytes

_PREVIEW_W = 360
_PREVIEW_H = 280


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


# ── Worker ────────────────────────────────────────────────────────────────────

class _Signals(QObject):
    finished = Signal(bytes, str)
    error    = Signal(str)
    progress = Signal(str)


class _Worker(QRunnable):
    def __init__(self, path: Path, threshold: float, signals: _Signals) -> None:
        super().__init__()
        self._path = path
        self._threshold = threshold
        self._signals = signals
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            self._signals.progress.emit("Analysing background colour…")
            result = remove_background(self._path, threshold=self._threshold)
            self._signals.progress.emit("Finalising…")
            buf = io.BytesIO()
            result.save(buf, format="PNG")
            self._signals.finished.emit(buf.getvalue(), self._path.stem)
        except Exception as exc:
            self._signals.error.emit(f"{type(exc).__name__}: {exc}")


# ── Checkerboard preview ──────────────────────────────────────────────────────

class _OriginalLabel(QWidget):
    """Shows the original image on a solid background (no checkerboard)."""

    def __init__(self, caption: str, w: int = _PREVIEW_W, h: int = _PREVIEW_H) -> None:
        super().__init__()
        self._caption = caption
        self._pixmap: Optional[QPixmap] = None
        self._info = ""
        self.setFixedSize(w, h)
        self._bg = QColor(30, 30, 30)

    def set_pixmap(self, px: QPixmap) -> None:
        self._pixmap = px
        self._info = f"{px.width()} × {px.height()}"
        self.update()

    def clear(self, msg: str = "") -> None:
        self._pixmap = None
        self._info = msg
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, self._bg)
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(w - 8, h - 28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((w - scaled.width()) // 2,
                         4 + (h - 28 - scaled.height()) // 2, scaled)
        elif self._info:
            p.setPen(QColor(140, 140, 140))
            p.drawText(QRect(0, 0, w, h - 24), Qt.AlignmentFlag.AlignCenter, self._info)
        p.fillRect(0, h - 24, w, 24, QColor(0, 0, 0, 130))
        p.setPen(QColor(255, 255, 255, 190))
        txt = self._caption + (f"  ·  {self._info}" if self._info and self._pixmap else "")
        p.drawText(QRect(8, h - 24, w - 16, 24), Qt.AlignmentFlag.AlignVCenter, txt)
        p.end()


class _CheckerLabel(QWidget):
    """Shows the result image on a checkerboard (reveals transparency)."""

    def __init__(self, caption: str, w: int = _PREVIEW_W, h: int = _PREVIEW_H) -> None:
        super().__init__()
        self._caption = caption
        self._pixmap: Optional[QPixmap] = None
        self._info = ""
        self.setFixedSize(w, h)
        self._c1 = QColor(55, 55, 55)
        self._c2 = QColor(38, 38, 38)

    def set_pixmap(self, px: QPixmap) -> None:
        self._pixmap = px
        self._info = f"{px.width()} × {px.height()}"
        self.update()

    def clear(self, msg: str = "") -> None:
        self._pixmap = None
        self._info = msg
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        sq = 14
        for row in range(h // sq + 1):
            for col in range(w // sq + 1):
                p.fillRect(col * sq, row * sq, sq, sq,
                           self._c1 if (row + col) % 2 == 0 else self._c2)
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(w - 8, h - 28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((w - scaled.width()) // 2,
                         4 + (h - 28 - scaled.height()) // 2, scaled)
        elif self._info:
            p.setPen(QColor(180, 180, 180))
            p.drawText(QRect(0, 0, w, h - 24), Qt.AlignmentFlag.AlignCenter, self._info)
        p.fillRect(0, h - 24, w, 24, QColor(0, 0, 0, 130))
        p.setPen(QColor(255, 255, 255, 190))
        txt = self._caption + (f"  ·  {self._info}" if self._info and self._pixmap else "")
        p.drawText(QRect(8, h - 24, w - 16, 24), Qt.AlignmentFlag.AlignVCenter, txt)
        p.end()


# ── Advanced brush canvas ─────────────────────────────────────────────────────

class _BrushCanvas(QWidget):
    """Paint keep (green) / remove (red) strokes on the result image.

    The strokes are composited onto the alpha mask when the user clicks
    'Apply brush strokes'.
    """

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._base_px: Optional[QPixmap] = None   # the auto-result pixmap
        self._overlay: Optional[QImage] = None    # RGBA brush strokes
        self._brush_mode = "keep"   # "keep" or "remove"
        self._brush_size = 20
        self._drawing = False
        self._last_pt: Optional[QPoint] = None
        self.setMinimumHeight(300)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setMouseTracking(True)

    def set_image(self, px: QPixmap) -> None:
        self._base_px = px
        self._overlay = QImage(px.size(), QImage.Format.Format_ARGB32)
        self._overlay.fill(Qt.GlobalColor.transparent)
        self.update()

    def set_mode(self, mode: str) -> None:
        self._brush_mode = mode

    def set_brush_size(self, size: int) -> None:
        self._brush_size = size

    def clear_strokes(self) -> None:
        if self._overlay:
            self._overlay.fill(Qt.GlobalColor.transparent)
            self.update()

    def get_stroke_mask(self) -> Optional[QImage]:
        return self._overlay

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._paint_at(event.position().toPoint())

    def mouseMoveEvent(self, event) -> None:
        if self._drawing and event.buttons() & Qt.MouseButton.LeftButton:
            self._paint_at(event.position().toPoint())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = False
            self._last_pt = None
            self.changed.emit()

    def _paint_at(self, pt: QPoint) -> None:
        if not self._overlay or not self._base_px:
            return
        # Map widget coords to image coords
        img_pt = self._widget_to_image(pt)
        if img_pt is None:
            return
        p = QPainter(self._overlay)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(0, 200, 0, 180) if self._brush_mode == "keep" else QColor(200, 0, 0, 180)
        pen = QPen(color, self._brush_size, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        if self._last_pt:
            p.drawLine(self._last_pt, img_pt)
        else:
            p.drawPoint(img_pt)
        p.end()
        self._last_pt = img_pt
        self.update()

    def _widget_to_image(self, pt: QPoint) -> Optional[QPoint]:
        if not self._base_px:
            return None
        iw, ih = self._base_px.width(), self._base_px.height()
        ww, wh = self.width(), self.height()
        scale = min(ww / iw, wh / ih)
        ox = int((ww - iw * scale) / 2)
        oy = int((wh - ih * scale) / 2)
        ix = int((pt.x() - ox) / scale)
        iy = int((pt.y() - oy) / scale)
        if 0 <= ix < iw and 0 <= iy < ih:
            return QPoint(ix, iy)
        return None

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Checkerboard bg
        sq = 12
        c1, c2 = QColor(50, 50, 50), QColor(35, 35, 35)
        for row in range(h // sq + 1):
            for col in range(w // sq + 1):
                p.fillRect(col * sq, row * sq, sq, sq,
                           c1 if (row + col) % 2 == 0 else c2)
        if self._base_px and not self._base_px.isNull():
            iw, ih = self._base_px.width(), self._base_px.height()
            scale = min(w / iw, h / ih)
            dw, dh = int(iw * scale), int(ih * scale)
            ox, oy = (w - dw) // 2, (h - dh) // 2
            p.drawPixmap(ox, oy, self._base_px.scaled(
                dw, dh, Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            if self._overlay:
                overlay_px = QPixmap.fromImage(self._overlay).scaled(
                    dw, dh, Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(ox, oy, overlay_px)
        else:
            p.setPen(QColor(120, 120, 120))
            p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                       "Run auto-removal first, then refine here")
        p.end()


# ── Drop zone ─────────────────────────────────────────────────────────────────

class _DropZone(QFrame):
    file_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setFixedHeight(110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setSpacing(6)
        icon = QLabel("◎")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("color: #d4956a; font-size: 22px;")
        l.addWidget(icon)
        title = QLabel("Drop an image here")
        title.setObjectName("h3")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(title)
        sub = QLabel("or click to browse  ·  JPG · PNG · WebP · BMP")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(sub)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select image", str(Path.home()),
                "Images (*.jpg *.jpeg *.png *.webp *.bmp)")
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
            if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                event.acceptProposedAction()
                self.file_dropped.emit(path)
                return


# ── Main page ─────────────────────────────────────────────────────────────────

class RemoveBgPage(QWidget):
    """Background remover with auto mode + advanced manual brush refinement."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        self._result_bytes: Optional[bytes] = None
        self._result_name: str = "output"
        self._current_path: Optional[Path] = None
        self._result_pil_image = None   # PIL Image kept for brush apply
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._signals: Optional[_Signals] = None
        self._threshold = 30.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        # Header
        eyebrow = QLabel("BACKGROUND REMOVER")
        eyebrow.setObjectName("eyebrow")
        il.addWidget(eyebrow)
        title = QLabel("Remove backgrounds instantly")
        title.setObjectName("h1")
        il.addWidget(title)
        sub = QLabel(
            "Auto mode uses colour analysis. Advanced mode lets you paint "
            "keep/remove strokes to refine complex edges.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        il.addWidget(sub)
        il.addWidget(_sep())

        # Mode tabs
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._auto_btn = QPushButton("Auto")
        self._auto_btn.setObjectName("chip")
        self._auto_btn.setCheckable(True)
        self._auto_btn.setChecked(True)
        self._adv_btn = QPushButton("Advanced")
        self._adv_btn.setObjectName("chip")
        self._adv_btn.setCheckable(True)
        self._mode_group.addButton(self._auto_btn)
        self._mode_group.addButton(self._adv_btn)
        self._auto_btn.clicked.connect(lambda: self._set_mode("auto"))
        self._adv_btn.clicked.connect(lambda: self._set_mode("advanced"))
        mode_row.addWidget(self._auto_btn)
        mode_row.addWidget(self._adv_btn)
        mode_row.addStretch(1)
        il.addLayout(mode_row)

        # Drop zone
        self._drop_zone = _DropZone()
        self._drop_zone.file_dropped.connect(self._on_file)
        il.addWidget(self._drop_zone)

        # Stacked: auto controls / advanced controls
        self._ctrl_stack = QStackedWidget()

        # ── Auto controls ──────────────────────────────────────────────
        auto_card = _surface()
        al = QVBoxLayout(auto_card)
        al.setContentsMargins(16, 12, 16, 12)
        al.setSpacing(8)
        thresh_head = QHBoxLayout()
        thresh_lbl = QLabel("Sensitivity")
        thresh_lbl.setObjectName("h3")
        self._thresh_val = QLabel(f"{int(self._threshold)}")
        self._thresh_val.setStyleSheet("font-weight: 600;")
        thresh_head.addWidget(thresh_lbl, 1)
        thresh_head.addWidget(self._thresh_val)
        al.addLayout(thresh_head)
        thresh_sub = QLabel("Higher = removes more background. Lower = keeps more edge detail.")
        thresh_sub.setObjectName("muted")
        thresh_sub.setWordWrap(True)
        al.addWidget(thresh_sub)
        self._thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self._thresh_slider.setRange(5, 80)
        self._thresh_slider.setValue(int(self._threshold))
        self._thresh_slider.valueChanged.connect(self._on_threshold_changed)
        al.addWidget(self._thresh_slider)
        legend = QHBoxLayout()
        for txt, align in (("Precise", Qt.AlignmentFlag.AlignLeft),
                            ("Balanced", Qt.AlignmentFlag.AlignCenter),
                            ("Aggressive", Qt.AlignmentFlag.AlignRight)):
            lbl = QLabel(txt)
            lbl.setObjectName("dim")
            lbl.setStyleSheet("font-size: 10px;")
            lbl.setAlignment(align)
            legend.addWidget(lbl, 1)
        al.addLayout(legend)
        self._rerun_btn = QPushButton("Re-run with new sensitivity")
        self._rerun_btn.setProperty("variant", "ghost")
        self._rerun_btn.setFixedHeight(30)
        self._rerun_btn.setEnabled(False)
        self._rerun_btn.clicked.connect(self._rerun)
        al.addWidget(self._rerun_btn)
        self._ctrl_stack.addWidget(auto_card)   # index 0

        # ── Advanced controls ──────────────────────────────────────────
        adv_card = _surface()
        adv_l = QVBoxLayout(adv_card)
        adv_l.setContentsMargins(16, 12, 16, 12)
        adv_l.setSpacing(10)

        adv_title = QLabel("Manual brush refinement")
        adv_title.setObjectName("h3")
        adv_l.addWidget(adv_title)
        adv_sub = QLabel(
            "Paint green to KEEP areas. Paint red to REMOVE areas. "
            "Click Apply to bake the strokes into the result.")
        adv_sub.setObjectName("muted")
        adv_sub.setWordWrap(True)
        adv_l.addWidget(adv_sub)

        brush_row = QHBoxLayout()
        brush_row.setSpacing(8)
        self._keep_btn = QPushButton("Keep (green)")
        self._keep_btn.setObjectName("chip")
        self._keep_btn.setCheckable(True)
        self._keep_btn.setChecked(True)
        self._remove_btn = QPushButton("Remove (red)")
        self._remove_btn.setObjectName("chip")
        self._remove_btn.setCheckable(True)
        brush_grp = QButtonGroup(self)
        brush_grp.setExclusive(True)
        brush_grp.addButton(self._keep_btn)
        brush_grp.addButton(self._remove_btn)
        self._keep_btn.clicked.connect(lambda: self._canvas.set_mode("keep"))
        self._remove_btn.clicked.connect(lambda: self._canvas.set_mode("remove"))
        brush_row.addWidget(self._keep_btn)
        brush_row.addWidget(self._remove_btn)
        brush_row.addStretch(1)
        adv_l.addLayout(brush_row)

        size_row = QHBoxLayout()
        size_row.setSpacing(10)
        size_lbl = QLabel("Brush size")
        size_lbl.setObjectName("muted")
        self._brush_slider = QSlider(Qt.Orientation.Horizontal)
        self._brush_slider.setRange(5, 60)
        self._brush_slider.setValue(20)
        self._brush_slider.valueChanged.connect(
            lambda v: self._canvas.set_brush_size(v))
        size_row.addWidget(size_lbl)
        size_row.addWidget(self._brush_slider, 1)
        adv_l.addLayout(size_row)

        # The brush canvas
        self._canvas = _BrushCanvas()
        self._canvas.setMinimumHeight(260)
        adv_l.addWidget(self._canvas)

        adv_btns = QHBoxLayout()
        adv_btns.setSpacing(8)
        self._clear_strokes_btn = QPushButton("Clear strokes")
        self._clear_strokes_btn.setProperty("variant", "ghost")
        self._clear_strokes_btn.setFixedHeight(30)
        self._clear_strokes_btn.clicked.connect(self._canvas.clear_strokes)
        self._apply_strokes_btn = QPushButton("Apply brush strokes")
        self._apply_strokes_btn.setProperty("variant", "primary")
        self._apply_strokes_btn.setFixedHeight(30)
        self._apply_strokes_btn.setEnabled(False)
        self._apply_strokes_btn.clicked.connect(self._apply_strokes)
        adv_btns.addWidget(self._clear_strokes_btn)
        adv_btns.addStretch(1)
        adv_btns.addWidget(self._apply_strokes_btn)
        adv_l.addLayout(adv_btns)
        self._ctrl_stack.addWidget(adv_card)   # index 1

        il.addWidget(self._ctrl_stack)

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

        # Before / After preview (auto mode only)
        self._preview_card = _surface()
        pl = QVBoxLayout(self._preview_card)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(12)
        ph = QHBoxLayout()
        preview_title = QLabel("Before / After")
        preview_title.setObjectName("h3")
        ph.addWidget(preview_title, 1)
        self._save_btn = QPushButton("Save PNG")
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.setFixedHeight(32)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        ph.addWidget(self._save_btn)
        pl.addLayout(ph)
        compare = QHBoxLayout()
        compare.setSpacing(12)
        self._before = _OriginalLabel("Original")
        self._after  = _CheckerLabel("Background removed")
        compare.addWidget(self._before)
        compare.addWidget(self._after)
        pl.addLayout(compare)
        il.addWidget(self._preview_card)
        il.addStretch(1)

        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(inner)
        outer.addWidget(sa, 1)

    # ── mode switching ────────────────────────────────────────────────────

    def _set_mode(self, mode: str) -> None:
        if mode == "auto":
            self._ctrl_stack.setCurrentIndex(0)
            self._preview_card.setVisible(True)
        else:
            self._ctrl_stack.setCurrentIndex(1)
            self._preview_card.setVisible(False)
            # Load current result into canvas
            if self._result_bytes:
                px = QPixmap()
                px.loadFromData(self._result_bytes)
                if not px.isNull():
                    self._canvas.set_image(px)
                    self._apply_strokes_btn.setEnabled(True)

    # ── drag & drop ───────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                self._on_file(path)
                break

    # ── internal ──────────────────────────────────────────────────────────

    def _on_threshold_changed(self, value: int) -> None:
        self._threshold = float(value)
        self._thresh_val.setText(str(value))

    def _rerun(self) -> None:
        if self._current_path:
            self._run(self._current_path)

    def _on_file(self, path: Path) -> None:
        self._current_path = path
        px = QPixmap(str(path))
        if not px.isNull():
            self._before.set_pixmap(px)
        self._after.clear("Processing…")
        self._run(path)

    def _run(self, path: Path) -> None:
        self._result_bytes = None
        self._save_btn.setEnabled(False)
        self._rerun_btn.setEnabled(False)
        self._apply_strokes_btn.setEnabled(False)
        self._status.setText("Starting…")
        self._status.setVisible(True)
        self._progress.setVisible(True)
        self._status.setStyleSheet("")
        self._signals = _Signals()
        self._signals.progress.connect(self._on_progress)
        self._signals.finished.connect(self._on_done)
        self._signals.error.connect(self._on_error)
        self._pool.start(_Worker(path, self._threshold, self._signals))

    def _on_progress(self, msg: str) -> None:
        self._status.setText(msg)

    def _on_done(self, png_bytes: bytes, name: str) -> None:
        self._result_bytes = png_bytes
        self._result_name = name
        self._progress.setVisible(False)
        self._status.setText(f"Done — {format_bytes(len(png_bytes))} transparent PNG")
        self._save_btn.setEnabled(True)
        self._rerun_btn.setEnabled(True)
        px = QPixmap()
        px.loadFromData(png_bytes)
        if not px.isNull():
            self._after.set_pixmap(px)
            self._canvas.set_image(px)
            self._apply_strokes_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._status.setText(f"Error: {msg}")
        self._status.setStyleSheet("color: #c0675a;")
        self._after.clear("Error")
        self._rerun_btn.setEnabled(bool(self._current_path))

    def _apply_strokes(self) -> None:
        """Bake the brush strokes into the alpha channel."""
        if not self._result_bytes:
            return
        stroke_img = self._canvas.get_stroke_mask()
        if stroke_img is None:
            return
        try:
            from PIL import Image as PILImage
            import io as _io

            # Load current result
            result = PILImage.open(_io.BytesIO(self._result_bytes)).convert("RGBA")
            w, h = result.size

            # Convert stroke QImage to PIL
            stroke_img_scaled = stroke_img.scaled(
                QSize(w, h), Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            ptr = stroke_img_scaled.bits()
            stroke_pil = PILImage.frombuffer(
                "RGBA", (w, h), bytes(ptr), "raw", "BGRA", 0, 1)

            r_ch, g_ch, b_ch, a_ch = result.split()
            stroke_r, stroke_g, stroke_b, stroke_a = stroke_pil.split()

            # (array module not needed — using list operations)
            a_data = list(a_ch.getdata())
            sr_data = list(stroke_r.getdata())
            sg_data = list(stroke_g.getdata())
            sa_data = list(stroke_a.getdata())

            new_a = []
            for i, (a, sr, sg, sa) in enumerate(zip(a_data, sr_data, sg_data, sa_data)):
                if sa > 50:
                    if sg > sr:   # green stroke = keep
                        new_a.append(255)
                    else:         # red stroke = remove
                        new_a.append(0)
                else:
                    new_a.append(a)

            from PIL import Image as _PI
            new_alpha = _PI.new("L", (w, h))
            new_alpha.putdata(new_a)
            final = _PI.merge("RGBA", (r_ch, g_ch, b_ch, new_alpha))

            buf = _io.BytesIO()
            final.save(buf, format="PNG")
            self._result_bytes = buf.getvalue()

            px = QPixmap()
            px.loadFromData(self._result_bytes)
            if not px.isNull():
                self._after.set_pixmap(px)
                self._canvas.set_image(px)
                self._canvas.clear_strokes()
            self._status.setText(f"Strokes applied — {format_bytes(len(self._result_bytes))}")
            self._status.setVisible(True)
        except Exception as exc:
            self._status.setText(f"Brush apply error: {exc}")
            self._status.setVisible(True)

    def _on_save(self) -> None:
        if not self._result_bytes:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save transparent PNG",
            str(Path.home() / f"{self._result_name}_nobg.png"),
            "PNG Image (*.png)")
        if dest:
            Path(dest).write_bytes(self._result_bytes)
