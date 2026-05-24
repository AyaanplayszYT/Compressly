"""Slim hero stats bar at the top of the dashboard."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .helpers import format_bytes


class HeroBanner(QFrame):
    """Compact stats bar: title + 3 stat tiles + progress bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("surface")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(20)

        # Left: app title
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        eyebrow = QLabel("COMPRESSLY")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Image Optimizer")
        title.setObjectName("h2")
        title_col.addWidget(eyebrow)
        title_col.addWidget(title)
        layout.addLayout(title_col, 0)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(
            "background-color: rgba(128,128,128,0.15); border: none; max-width: 1px;"
        )
        layout.addWidget(div)

        # Stats
        self._files_val, files_tile = self._stat("Files")
        self._saved_val, saved_tile = self._stat("Saved")
        self._pct_val, pct_tile = self._stat("Reduction")
        layout.addWidget(files_tile, 1)
        layout.addWidget(saved_tile, 1)
        layout.addWidget(pct_tile, 1)

        # Progress
        prog_col = QVBoxLayout()
        prog_col.setSpacing(4)
        prog_col.setContentsMargins(0, 0, 0, 0)
        self._prog_label = QLabel("Ready")
        self._prog_label.setObjectName("dim")
        self._prog_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFixedHeight(5)
        self._progress.setFixedWidth(140)
        prog_col.addStretch(1)
        prog_col.addWidget(self._prog_label)
        prog_col.addWidget(self._progress)
        layout.addLayout(prog_col, 0)

    def update_stats(
        self,
        *,
        completed: int,
        total: int,
        saved_bytes: int,
        reduction_pct: float,
    ) -> None:
        self._files_val.setText(f"{completed}/{total}")
        self._saved_val.setText(format_bytes(saved_bytes))
        self._pct_val.setText(f"{reduction_pct:.0f}%")
        if total <= 0:
            self._progress.setRange(0, 1)
            self._progress.setValue(0)
            self._prog_label.setText("Ready")
        else:
            self._progress.setRange(0, total)
            self._progress.setValue(completed)
            self._prog_label.setText(
                "Done" if completed >= total else f"{completed}/{total}"
            )

    def _stat(self, label: str) -> tuple[QLabel, QWidget]:
        tile = QWidget()
        col = QVBoxLayout(tile)
        col.setSpacing(1)
        col.setContentsMargins(0, 0, 0, 0)
        eyebrow = QLabel(label.upper())
        eyebrow.setObjectName("eyebrow")
        value = QLabel("0")
        value.setObjectName("stat")
        value.setStyleSheet("font-size: 20px; font-weight: 700;")
        col.addWidget(eyebrow)
        col.addWidget(value)
        return value, tile
