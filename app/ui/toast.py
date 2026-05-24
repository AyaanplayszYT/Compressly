"""Lightweight in-window toast notifications."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

ToastLevel = Literal["success", "info", "error"]

_ICONS = {"success": "✓", "info": "i", "error": "!"}


class ToastManager:
    """Stack toasts at the bottom-right of a parent widget."""

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._toasts: list[QFrame] = []

    def show(self, message: str, level: ToastLevel = "info", duration_ms: int = 3200) -> None:
        toast = _Toast(self._parent, message, level)
        toast.show()
        self._toasts.append(toast)
        self._reflow()

        QTimer.singleShot(duration_ms, lambda t=toast: self._dismiss(t))

    def _dismiss(self, toast: QFrame) -> None:
        if toast not in self._toasts:
            return
        self._toasts.remove(toast)
        anim = QPropertyAnimation(toast.graphicsEffect(), b"opacity", toast)
        anim.setDuration(220)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(toast.deleteLater)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        QTimer.singleShot(40, self._reflow)

    def _reflow(self) -> None:
        if not self._toasts:
            return
        margin = 18
        gap = 10
        parent_w = self._parent.width()
        parent_h = self._parent.height()
        y = parent_h - margin
        for toast in reversed(self._toasts):
            toast.adjustSize()
            x = parent_w - toast.width() - margin
            y -= toast.height()
            toast.move(QPoint(x, y))
            y -= gap


class _Toast(QFrame):
    def __init__(self, parent: QWidget, message: str, level: ToastLevel) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setProperty("level", level)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        icon = QLabel(_ICONS.get(level, "i"))
        icon.setObjectName("h3")
        icon.setFixedWidth(18)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if level == "success":
            icon.setStyleSheet("color: #4ade80;")
        elif level == "error":
            icon.setStyleSheet("color: #f87171;")
        else:
            icon.setStyleSheet("color: #a78bfa;")

        label = QLabel(message)
        label.setStyleSheet("color: #ededf3;")
        label.setWordWrap(False)
        label.setMaximumWidth(360)

        layout.addWidget(icon)
        layout.addWidget(label)

        # Soft shadow + fade-in
        opacity = QGraphicsOpacityEffect(self)
        opacity.setOpacity(0.0)
        self.setGraphicsEffect(opacity)
        anim = QPropertyAnimation(opacity, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        # Re-apply stylesheet for the property selector to take effect.
        self.style().unpolish(self)
        self.style().polish(self)

        # Tiny outline color hint via palette (works around QSS specificity)
        _ = QColor
