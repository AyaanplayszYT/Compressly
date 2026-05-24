"""Drop zone — styled like Claude's input box."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..engine import is_supported_image


def _safe_paths(mime: QMimeData) -> List[Path]:
    paths: List[Path] = []
    if not mime.hasUrls():
        return paths
    for url in mime.urls():
        try:
            local = url.toLocalFile()
        except Exception:
            continue
        if not local:
            continue
        try:
            p = Path(local).resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        paths.append(p)
    return paths


class DropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        compact: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setProperty("hover", False)
        self._compact = compact

        layout = QVBoxLayout(self)

        if compact:
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(0)

            row = QHBoxLayout()
            row.setSpacing(10)
            icon = QLabel("↑")
            icon.setStyleSheet("color: #9e9b94; font-size: 14px;")
            lbl = QLabel("Add more images")
            lbl.setObjectName("muted")
            row.addWidget(icon)
            row.addWidget(lbl, 1)

            browse = QPushButton("Browse")
            browse.setProperty("variant", "ghost")
            browse.setFixedHeight(28)
            browse.clicked.connect(self._browse_files)
            row.addWidget(browse)
            layout.addLayout(row)

        else:
            layout.setContentsMargins(32, 28, 32, 28)
            layout.setSpacing(12)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon = QLabel("↓")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet("color: #9e9b94; font-size: 24px;")
            layout.addWidget(icon)

            title = QLabel("Drop images here")
            title.setObjectName("h3")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title)

            sub = QLabel("or click to browse files and folders")
            sub.setObjectName("muted")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(sub)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)
            btn_row.addStretch(1)

            files_btn = QPushButton("Browse files")
            files_btn.setProperty("variant", "primary")
            files_btn.setFixedHeight(34)
            files_btn.clicked.connect(self._browse_files)

            folder_btn = QPushButton("Browse folder")
            folder_btn.setFixedHeight(34)
            folder_btn.clicked.connect(self._browse_folder)

            btn_row.addWidget(files_btn)
            btn_row.addWidget(folder_btn)
            btn_row.addStretch(1)
            layout.addLayout(btn_row)

        if compact:
            self._on_click: Callable[[], None] | None = self._browse_files
        else:
            self._on_click = None

    def dispatch(self, items: Iterable[Path]) -> None:
        valid: List[Path] = []
        for p in items:
            try:
                p = Path(p).resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if p.is_dir() or is_supported_image(p):
                valid.append(p)
        if valid:
            self.files_dropped.emit(valid)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_hover(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_hover(False)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_hover(False)
        paths = _safe_paths(event.mimeData())
        if paths:
            event.acceptProposedAction()
            self.dispatch(paths)
        else:
            event.ignore()

    def mousePressEvent(self, event) -> None:
        if self._on_click and event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)

    def _set_hover(self, value: bool) -> None:
        if self.property("hover") == value:
            return
        self.setProperty("hover", value)
        self.style().unpolish(self)
        self.style().polish(self)

    def _browse_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select images", str(Path.home()),
            "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff)",
        )
        if files:
            self.dispatch(Path(f) for f in files)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select folder", str(Path.home())
        )
        if folder:
            self.dispatch([Path(folder)])
