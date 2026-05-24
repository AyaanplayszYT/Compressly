"""Small UI helpers."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QWidget


def add_soft_shadow(widget: QWidget, *, blur: int = 32, alpha: int = 70) -> None:
    """Apply a soft drop shadow under `widget`."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 8)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet("background-color: rgba(255,255,255,0.06); border: none;")
    return line


def format_bytes(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{int(num_bytes)} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def elide_path(text: str, max_chars: int = 60) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 2 - 1
    tail = max_chars - head - 1
    return f"{text[:head]}…{text[-tail:]}"


def configure_window_alignment(widget: QWidget) -> None:
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
