"""Before/After split slider widget.

Drag the divider left/right to compare two images.
Used on the compress page to show original vs compressed quality.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import (
    QColor,
    QCursor,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import QWidget


class SplitView(QWidget):
    """Drag-to-compare before/after widget.

    Set images with set_before() / set_after().
    The divider starts at 50% and can be dragged.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._before: Optional[QPixmap] = None
        self._after:  Optional[QPixmap] = None
        self._split = 0.5          # 0.0 → 1.0
        self._dragging = False
        self._before_label = "Before"
        self._after_label  = "After"
        self.setMinimumHeight(200)
        self.setCursor(QCursor(Qt.CursorShape.SplitHCursor))
        self.setMouseTracking(True)

    # ── public ────────────────────────────────────────────────────────────

    def set_before(self, px: Optional[QPixmap], label: str = "Original") -> None:
        self._before = px
        self._before_label = label
        self.update()

    def set_after(self, px: Optional[QPixmap], label: str = "Compressed") -> None:
        self._after = px
        self._after_label = label
        self.update()

    def clear(self) -> None:
        self._before = None
        self._after  = None
        self.update()

    def reset_split(self) -> None:
        self._split = 0.5
        self.update()

    # ── events ────────────────────────────────────────────────────────────

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

    # ── paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        split_x = int(w * self._split)

        # Background
        p.fillRect(0, 0, w, h, QColor(30, 30, 30))

        # Checkerboard (shows when images have transparency)
        sq = 12
        c1, c2 = QColor(45, 45, 45), QColor(35, 35, 35)
        for row in range(h // sq + 1):
            for col in range(w // sq + 1):
                p.fillRect(col * sq, row * sq, sq, sq,
                           c1 if (row + col) % 2 == 0 else c2)

        if self._before is None and self._after is None:
            p.setPen(QColor(100, 100, 100))
            p.drawText(
                QRect(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter,
                "Compress an image to see the before/after comparison",
            )
            p.end()
            return

        # Helper: scale a pixmap to fit the widget while keeping aspect ratio
        def _fit(px: QPixmap) -> tuple[QPixmap, int, int]:
            scaled = px.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            ox = (w - scaled.width()) // 2
            oy = (h - scaled.height()) // 2
            return scaled, ox, oy

        # Before (left side, clipped to split_x)
        if self._before and not self._before.isNull():
            scaled, ox, oy = _fit(self._before)
            p.save()
            p.setClipRect(0, 0, split_x, h)
            p.drawPixmap(ox, oy, scaled)
            p.restore()

        # After (right side, clipped from split_x)
        if self._after and not self._after.isNull():
            scaled, ox, oy = _fit(self._after)
            p.save()
            p.setClipRect(split_x, 0, w - split_x, h)
            p.drawPixmap(ox, oy, scaled)
            p.restore()

        # Divider line
        p.setPen(QColor(255, 255, 255, 200))
        p.drawLine(split_x, 0, split_x, h)

        # Handle circle
        cx, cy = split_x, h // 2
        r = 16
        p.setBrush(QColor(255, 255, 255))
        p.setPen(QColor(180, 180, 180))
        p.drawEllipse(QPoint(cx, cy), r, r)
        # Arrows inside handle
        p.setPen(QColor(80, 80, 80))
        p.drawText(
            QRect(cx - r, cy - r, r * 2, r * 2),
            Qt.AlignmentFlag.AlignCenter,
            "⇔",
        )

        # Labels
        self._draw_label(p, self._before_label, 8, 8, left=True)
        self._draw_label(p, self._after_label, w - 8, 8, left=False)

        p.end()

    def _draw_label(
        self, p: QPainter, text: str, x: int, y: int, left: bool
    ) -> None:
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text) + 16
        th = fm.height() + 8
        rx = x if left else x - tw
        path = QPainterPath()
        path.addRoundedRect(rx, y, tw, th, 5, 5)
        p.fillPath(path, QColor(0, 0, 0, 140))
        p.setPen(QColor(255, 255, 255, 200))
        p.drawText(QRect(rx, y, tw, th), Qt.AlignmentFlag.AlignCenter, text)
