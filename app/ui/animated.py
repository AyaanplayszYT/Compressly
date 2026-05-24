"""Reusable animation helpers.

FadingStack  — QStackedWidget with a smooth crossfade between pages.
fade_in      — Fade a widget in from opacity 0 → 1.
slide_down   — Slide a widget in from above (for queue rows, toasts, etc.)
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QTimer,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QStackedWidget,
    QWidget,
)


# ── Fading stacked widget ─────────────────────────────────────────────────────

class FadingStack(QStackedWidget):
    """QStackedWidget that crossfades between pages.

    Duration: 160 ms, OutCubic easing — fast enough to feel snappy,
    slow enough to feel smooth.
    """

    DURATION = 160

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._animating = False

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        if index == self.currentIndex() or self._animating:
            super().setCurrentIndex(index)
            return
        self._fade_to(index)

    def setCurrentWidget(self, widget: QWidget) -> None:  # noqa: N802
        self.setCurrentIndex(self.indexOf(widget))

    def _fade_to(self, target: int) -> None:
        current_w = self.currentWidget()
        if current_w is None:
            super().setCurrentIndex(target)
            return

        # Ensure target widget is visible but transparent
        target_w = self.widget(target)
        if target_w is None:
            super().setCurrentIndex(target)
            return

        self._animating = True

        # Fade out current
        out_effect = QGraphicsOpacityEffect(current_w)
        out_effect.setOpacity(1.0)
        current_w.setGraphicsEffect(out_effect)

        out_anim = QPropertyAnimation(out_effect, b"opacity", self)
        out_anim.setDuration(self.DURATION)
        out_anim.setStartValue(1.0)
        out_anim.setEndValue(0.0)
        out_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _switch() -> None:
            super(FadingStack, self).setCurrentIndex(target)
            # Clean up old effect
            if current_w:
                current_w.setGraphicsEffect(None)
            # Fade in new
            in_effect = QGraphicsOpacityEffect(target_w)
            in_effect.setOpacity(0.0)
            target_w.setGraphicsEffect(in_effect)

            in_anim = QPropertyAnimation(in_effect, b"opacity", self)
            in_anim.setDuration(self.DURATION)
            in_anim.setStartValue(0.0)
            in_anim.setEndValue(1.0)
            in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def _done() -> None:
                target_w.setGraphicsEffect(None)
                self._animating = False

            in_anim.finished.connect(_done)
            in_anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        out_anim.finished.connect(_switch)
        out_anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


# ── Utility functions ─────────────────────────────────────────────────────────

def fade_in(widget: QWidget, duration: int = 200, delay: int = 0) -> None:
    """Fade `widget` in from opacity 0 → 1."""
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _start() -> None:
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _done() -> None:
        widget.setGraphicsEffect(None)

    anim.finished.connect(_done)

    if delay > 0:
        QTimer.singleShot(delay, _start)
    else:
        _start()


def slide_fade_in(widget: QWidget, duration: int = 220, offset: int = 12) -> None:
    """Slide `widget` in from `offset` pixels below its final position while fading in."""
    # Opacity
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    op_anim = QPropertyAnimation(effect, b"opacity", widget)
    op_anim.setDuration(duration)
    op_anim.setStartValue(0.0)
    op_anim.setEndValue(1.0)
    op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # Position — move from (x, y+offset) to (x, y)
    start_pos = widget.pos()
    widget.move(start_pos.x(), start_pos.y() + offset)

    pos_anim = QPropertyAnimation(widget, b"pos", widget)
    pos_anim.setDuration(duration)
    pos_anim.setStartValue(widget.pos())
    pos_anim.setEndValue(start_pos)
    pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(op_anim)
    group.addAnimation(pos_anim)

    def _done() -> None:
        widget.setGraphicsEffect(None)

    group.finished.connect(_done)
    group.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)
