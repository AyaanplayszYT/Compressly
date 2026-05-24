"""Before/After image preview panel.

Shows the selected queue item's original vs compressed image side-by-side
with a draggable split slider, plus metadata (dimensions, size, savings).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QPoint,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..models import ImageJob, JobStatus
from .helpers import format_bytes


class _SplitView(QWidget):
    """Drag-to-compare before/after widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(QCursor(Qt.CursorShape.SplitHCursor))

        self._before: Optional[QPixmap] = None
        self._after: Optional[QPixmap] = None
        self._split = 0.5          # 0.0 → 1.0
        self._dragging = False
        self._placeholder = True

    def set_images(self, before: Optional[Path], after: Optional[Path]) -> None:
        self._before = QPixmap(str(before)) if before and before.exists() else None
        self._after = QPixmap(str(after)) if after and after.exists() else None
        self._placeholder = self._before is None and self._after is None
        self._split = 0.5
        self.update()

    def clear(self) -> None:
        self._before = None
        self._after = None
        self._placeholder = True
        self.update()

    # ── mouse ──────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._update_split(event.position().x())

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._update_split(event.position().x())

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False

    def _update_split(self, x: float) -> None:
        w = max(1, self.width())
        self._split = max(0.02, min(0.98, x / w))
        self.update()

    # ── paint ──────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect()
        w, h = rect.width(), rect.height()
        split_x = int(w * self._split)

        # Background
        painter.fillRect(rect, QColor("#111118"))

        # Checkerboard for transparency
        self._draw_checker(painter, rect)

        if self._placeholder:
            painter.setPen(QColor("#6b6882"))
            font = QFont("Segoe UI", 12)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             "Select a compressed image\nto see the before/after comparison")
            return

        # Before (left side)
        if self._before and not self._before.isNull():
            scaled = self._before.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            ox = (w - scaled.width()) // 2
            oy = (h - scaled.height()) // 2
            clip = QRect(0, 0, split_x, h)
            painter.setClipRect(clip)
            painter.drawPixmap(ox, oy, scaled)
            painter.setClipping(False)

        # After (right side)
        if self._after and not self._after.isNull():
            scaled = self._after.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            ox = (w - scaled.width()) // 2
            oy = (h - scaled.height()) // 2
            clip = QRect(split_x, 0, w - split_x, h)
            painter.setClipRect(clip)
            painter.drawPixmap(ox, oy, scaled)
            painter.setClipping(False)

        # Divider line
        pen = QPen(QColor(255, 255, 255, 200), 2)
        painter.setPen(pen)
        painter.drawLine(split_x, 0, split_x, h)

        # Handle circle
        cx, cy = split_x, h // 2
        r = 14
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(QPen(QColor("#8b5cf6"), 2))
        painter.drawEllipse(QPoint(cx, cy), r, r)

        # Arrows inside handle
        painter.setPen(QPen(QColor("#8b5cf6"), 2))
        painter.drawText(
            QRect(cx - r, cy - r, r * 2, r * 2),
            Qt.AlignmentFlag.AlignCenter,
            "⇔",
        )

        # Labels
        self._draw_label(painter, "BEFORE", QRect(8, 8, 80, 22), left=True)
        self._draw_label(painter, "AFTER", QRect(w - 88, 8, 80, 22), left=False)

    def _draw_checker(self, painter: QPainter, rect: QRect) -> None:
        size = 12
        c1 = QColor("#1a1828")
        c2 = QColor("#141320")
        for row in range(rect.height() // size + 1):
            for col in range(rect.width() // size + 1):
                color = c1 if (row + col) % 2 == 0 else c2
                painter.fillRect(col * size, row * size, size, size, color)

    def _draw_label(self, painter: QPainter, text: str, rect: QRect, left: bool) -> None:
        painter.save()
        painter.setBrush(QColor(0, 0, 0, 140))
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 6, 6)
        painter.drawPath(path)
        painter.setPen(QColor(255, 255, 255, 200))
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class PreviewPanel(QFrame):
    """Right-side panel showing before/after comparison + file metadata."""

    open_in_explorer_requested = Signal(object)  # Path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumWidth(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        eyebrow = QLabel("PREVIEW")
        eyebrow.setObjectName("eyebrow")
        self._title = QLabel("No selection")
        self._title.setObjectName("h3")
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_col.addWidget(eyebrow)
        title_col.addWidget(self._title)
        hdr.addLayout(title_col, 1)

        self._open_btn = QPushButton("Show in Explorer")
        self._open_btn.setProperty("variant", "ghost")
        self._open_btn.setFixedHeight(30)
        self._open_btn.setVisible(False)
        self._open_btn.clicked.connect(self._on_open)
        hdr.addWidget(self._open_btn)
        layout.addLayout(hdr)

        # Split view
        self._split = _SplitView()
        layout.addWidget(self._split, 1)

        # Metadata grid
        meta_frame = QFrame()
        meta_frame.setObjectName("cardFlat")
        meta_layout = QVBoxLayout(meta_frame)
        meta_layout.setContentsMargins(12, 10, 12, 10)
        meta_layout.setSpacing(6)

        self._rows: dict[str, QLabel] = {}
        for key, label in (
            ("original", "Original"),
            ("output", "Compressed"),
            ("savings", "Saved"),
            ("dimensions", "Dimensions"),
            ("format", "Format"),
            ("duration", "Time"),
        ):
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setObjectName("dim")
            lbl.setFixedWidth(90)
            val = QLabel("—")
            val.setObjectName("muted")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            meta_layout.addLayout(row)
            self._rows[key] = val

        layout.addWidget(meta_frame)

        self._current_output: Optional[Path] = None

    # ── public ────────────────────────────────────────────────────────────

    def show_job(self, job: ImageJob) -> None:
        self._title.setText(job.source.name)
        self._current_output = job.output_path

        if job.status is JobStatus.DONE and job.output_path:
            self._split.set_images(job.source, job.output_path)
            self._open_btn.setVisible(True)
            self._rows["original"].setText(format_bytes(job.original_size))
            self._rows["output"].setText(format_bytes(job.output_size))
            savings = job.savings_bytes
            pct = job.savings_percent
            self._rows["savings"].setText(
                f"{format_bytes(savings)}  (−{pct:.0f}%)"
            )
            self._rows["savings"].setStyleSheet("color: #4ade80; font-weight: 600;")
            dims = (
                f"{job.output_width}×{job.output_height}"
                if job.output_width else "—"
            )
            self._rows["dimensions"].setText(dims)
            self._rows["format"].setText(
                job.output_path.suffix.lstrip(".").upper()
            )
            self._rows["duration"].setText(f"{job.duration_ms} ms")
        elif job.status is JobStatus.RUNNING:
            self._split.clear()
            self._open_btn.setVisible(False)
            self._rows["original"].setText(format_bytes(job.original_size) if job.original_size else "—")
            for k in ("output", "savings", "dimensions", "format", "duration"):
                self._rows[k].setText("Compressing…")
                self._rows[k].setStyleSheet("color: #a78bfa;")
        elif job.status is JobStatus.ERROR:
            self._split.clear()
            self._open_btn.setVisible(False)
            self._rows["output"].setText(job.error_message or "Error")
            self._rows["output"].setStyleSheet("color: #f87171;")
        else:
            self._split.set_images(job.source, None)
            self._open_btn.setVisible(False)
            self._rows["original"].setText(format_bytes(job.original_size) if job.original_size else "—")
            for k in ("output", "savings", "dimensions", "format", "duration"):
                self._rows[k].setText("—")
                self._rows[k].setStyleSheet("")

    def clear(self) -> None:
        self._title.setText("No selection")
        self._split.clear()
        self._open_btn.setVisible(False)
        self._current_output = None
        for val in self._rows.values():
            val.setText("—")
            val.setStyleSheet("")

    # ── internal ──────────────────────────────────────────────────────────

    def _on_open(self) -> None:
        if self._current_output and self._current_output.exists():
            # Select the file in Windows Explorer
            try:
                subprocess.run(
                    ["explorer", "/select,", str(self._current_output)],
                    check=False,
                )
            except OSError:
                pass
