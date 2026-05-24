"""File queue list widget."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import ImageJob, JobStatus
from .helpers import elide_path, format_bytes

_THUMB = 48


def _thumb(path: Path) -> QPixmap:
    pm = QPixmap(str(path))
    if pm.isNull():
        pm = QPixmap(_THUMB, _THUMB)
        pm.fill(Qt.GlobalColor.darkGray)
        return pm
    return pm.scaled(
        _THUMB, _THUMB,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )


class _QueueRow(QWidget):
    """One file row.

    WA_StyledBackground=True is critical — without it Qt ignores the
    background-color set by the #queueRow QSS rule on embedded widgets.
    """

    download_requested = Signal(object)   # Path (output_path)

    def __init__(self, source: Path, original_size: int) -> None:
        super().__init__()
        self.setObjectName("queueRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(64)
        self._output_path: Optional[Path] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # Thumbnail
        self._thumb_lbl = QLabel()
        self._thumb_lbl.setFixedSize(_THUMB, _THUMB)
        self._thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_lbl.setStyleSheet(
            "border-radius: 6px; background-color: rgba(255,255,255,0.05);"
        )
        pm = _thumb(source)
        if pm.width() > _THUMB or pm.height() > _THUMB:
            pm = pm.scaled(_THUMB, _THUMB,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        self._thumb_lbl.setPixmap(pm)

        # Text column
        text = QVBoxLayout()
        text.setSpacing(2)
        text.setContentsMargins(0, 0, 0, 0)

        self._name = QLabel(source.name)
        self._name.setStyleSheet("font-weight: 500; font-size: 13px;")

        self._meta = QLabel(format_bytes(original_size))
        self._meta.setObjectName("dim")

        self._folder = QLabel(elide_path(str(source.parent), 60))
        self._folder.setObjectName("dim")
        self._folder.setStyleSheet("font-size: 10px;")

        text.addWidget(self._name)
        text.addWidget(self._meta)
        text.addWidget(self._folder)

        # Right side: status + download button
        right = QVBoxLayout()
        right.setSpacing(4)
        right.setContentsMargins(0, 0, 0, 0)
        right.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._status = QLabel("Queued")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._status.setFixedWidth(150)
        self._status.setObjectName("dim")

        self._dl_btn = QPushButton("Save")
        self._dl_btn.setProperty("variant", "ghost")
        self._dl_btn.setFixedHeight(26)
        self._dl_btn.setFixedWidth(60)
        self._dl_btn.setVisible(False)
        self._dl_btn.clicked.connect(self._on_download)

        right.addWidget(self._status)
        right.addWidget(self._dl_btn, 0, Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self._thumb_lbl, 0)
        layout.addLayout(text, 1)
        layout.addLayout(right, 0)

    def update_from_job(self, job: ImageJob) -> None:
        if job.status is JobStatus.RUNNING:
            self._status.setText("Compressing…")
            self._status.setStyleSheet("font-size: 11px; font-weight: 500; color: #d4956a;")
            self._dl_btn.setVisible(False)
        elif job.status is JobStatus.DONE:
            pct = job.savings_percent
            self._status.setText(f"{format_bytes(job.output_size)}  −{pct:.0f}%")
            self._status.setStyleSheet("font-size: 11px; font-weight: 600; color: #5a9e6f;")
            self._meta.setText(f"Saved {format_bytes(job.savings_bytes)}")
            self._meta.setStyleSheet("font-size: 11px; color: #5a9e6f;")
            self._output_path = job.output_path
            self._dl_btn.setVisible(True)
            # Update thumbnail to show compressed version
            if job.output_path and job.output_path.exists():
                pm = _thumb(job.output_path)
                if pm.width() > _THUMB or pm.height() > _THUMB:
                    pm = pm.scaled(_THUMB, _THUMB,
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                self._thumb_lbl.setPixmap(pm)
        elif job.status is JobStatus.ERROR:
            self._status.setText(job.error_message or "Error")
            self._status.setStyleSheet("font-size: 11px; color: #c0675a;")
            self._dl_btn.setVisible(False)
        elif job.status is JobStatus.CANCELLED:
            self._status.setText("Cancelled")
            self._status.setStyleSheet("")
            self._status.setObjectName("dim")
            self._dl_btn.setVisible(False)
        else:
            self._status.setText("Queued")
            self._status.setStyleSheet("")
            self._status.setObjectName("dim")
            self._dl_btn.setVisible(False)

    def _on_download(self) -> None:
        if not (self._output_path and self._output_path.exists()):
            return

        from PySide6.QtWidgets import QFileDialog

        ext = self._output_path.suffix.lower().lstrip(".")
        ext_map = {
            "jpg": "JPEG Image (*.jpg)",
            "jpeg": "JPEG Image (*.jpeg)",
            "png": "PNG Image (*.png)",
            "webp": "WebP Image (*.webp)",
        }
        file_filter = ext_map.get(ext, f"{ext.upper()} File (*.{ext})")

        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save compressed image",
            str(Path.home() / self._output_path.name),
            file_filter,
        )
        if not dest:
            return

        try:
            shutil.copy2(str(self._output_path), dest)
        except OSError:
            pass


class QueueWidget(QWidget):
    """Scrollable file queue with header."""

    clear_requested = Signal()
    row_selected    = Signal(object)   # ImageJob

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("surface")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # Header
        header = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.setSpacing(1)

        eyebrow = QLabel("QUEUE")
        eyebrow.setObjectName("eyebrow")
        self._summary = QLabel("0 files")
        self._summary.setObjectName("h3")
        left_col.addWidget(eyebrow)
        left_col.addWidget(self._summary)

        self._clear_btn = QPushButton("Clear all")
        self._clear_btn.setProperty("variant", "ghost")
        self._clear_btn.setFixedHeight(30)
        self._clear_btn.clicked.connect(self.clear_requested.emit)

        header.addLayout(left_col, 1)
        header.addWidget(self._clear_btn, 0)
        outer.addLayout(header)

        # Separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.07);")
        outer.addWidget(sep)

        # List
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setSpacing(0)
        self._list.setUniformItemSizes(False)
        self._list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self._list, 1)

        self._rows: Dict[int, _QueueRow] = {}
        self._jobs: Dict[int, object] = {}   # index → ImageJob
        self._list.itemClicked.connect(self._on_item_clicked)

    def reset(self) -> None:
        self._list.clear()
        self._rows.clear()
        self._jobs.clear()
        self._summary.setText("0 files")

    def populate(self, sources: List[Path], sizes: List[int]) -> None:
        self.reset()
        for index, (src, size) in enumerate(zip(sources, sizes)):
            row = _QueueRow(src, size)
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 70))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
            self._rows[index] = row
        n = len(sources)
        self._summary.setText(f"{n} file{'s' if n != 1 else ''}")

    def update_job(self, index: int, job: ImageJob) -> None:
        row = self._rows.get(index)
        if row:
            row.update_from_job(job)
        self._jobs[index] = job

    def selected_index(self) -> Optional[int]:
        idx = self._list.currentRow()
        return idx if idx >= 0 else None

    def _on_item_clicked(self, item) -> None:
        idx = self._list.row(item)
        job = self._jobs.get(idx)
        if job is not None:
            self.row_selected.emit(job)
