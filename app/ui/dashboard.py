"""Dashboard — Claude-style layout.

Empty state: centered drop zone with greeting.
Loaded state: left queue + right controls panel.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from ..engine import iter_image_paths
from ..models import CompressionSettings, ImageJob
from .animated import FadingStack, fade_in
from .controls import ControlsPanel
from .dropzone import DropZone
from .queue import QueueWidget
from .split_view import SplitView


class _StatsBar(QWidget):
    """Slim stats row shown above the queue."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)

        self._files = self._stat("Files", "0/0")
        self._saved = self._stat("Saved", "0 B")
        self._pct   = self._stat("Reduction", "0%")

        for w in (self._files[0], self._saved[0], self._pct[0]):
            layout.addWidget(w)
        layout.addStretch(1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFixedSize(160, 4)
        layout.addWidget(self._progress, 0, Qt.AlignmentFlag.AlignVCenter)

    def _stat(self, label: str, value: str):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)
        lbl = QLabel(label)
        lbl.setObjectName("dim")
        val = QLabel(value)
        val.setObjectName("muted")
        val.setStyleSheet("font-weight: 500;")
        l.addWidget(lbl)
        l.addWidget(val)
        return w, val

    def update(self, *, completed: int, total: int,
               saved_bytes: int, reduction_pct: float) -> None:
        from .helpers import format_bytes
        self._files[1].setText(f"{completed}/{total}")
        self._saved[1].setText(format_bytes(saved_bytes))
        self._pct[1].setText(f"{reduction_pct:.0f}%")
        if total <= 0:
            self._progress.setRange(0, 1)
            self._progress.setValue(0)
        else:
            self._progress.setRange(0, total)
            self._progress.setValue(completed)


class _EmptyState(QWidget):
    """Centered drop zone shown when no files are loaded."""

    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 0, 40, 60)
        layout.setSpacing(0)
        layout.addStretch(1)

        # Greeting — uses QSS h1 so it respects the theme
        greeting = QLabel("Compressly")
        greeting.setObjectName("h1")
        greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        greeting.setStyleSheet(
            "font-size: 32px; font-weight: 400; letter-spacing: -1px;"
        )
        layout.addWidget(greeting)
        layout.addSpacing(6)

        sub = QLabel("Drop images to compress, convert, and resize.")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(4)
        layout.addWidget(sub)
        layout.addSpacing(28)

        # Drop zone
        self._drop = DropZone()
        self._drop.files_dropped.connect(self.files_dropped.emit)
        self._drop.setFixedHeight(160)
        self._drop.setMaximumWidth(680)
        self._drop.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        center_row = QHBoxLayout()
        center_row.addStretch(1)
        center_row.addWidget(self._drop, 0)
        center_row.addStretch(1)
        layout.addLayout(center_row)
        layout.addSpacing(20)

        # Format chips — use QSS-friendly inline style with palette-safe colors
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        chips_row.addStretch(1)
        for label in ("JPG", "PNG", "WebP", "BMP", "GIF", "TIFF"):
            chip = QLabel(label)
            chip.setObjectName("formatChip")
            chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            chips_row.addWidget(chip)
        chips_row.addStretch(1)
        layout.addLayout(chips_row)

        layout.addStretch(1)


class DashboardPage(QWidget):
    """Main dashboard page."""

    files_added = Signal(list)
    run_requested = Signal()
    cancel_requested = Signal()
    output_dir_changed = Signal(object)
    settings_changed = Signal(object)
    download_all_requested = Signal()   # triggers ZIP export in MainWindow

    def __init__(
        self, settings: CompressionSettings, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self._sources: List[Path] = []
        self._sizes: List[int] = []
        self._output_dir: Optional[Path] = settings.output_dir

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Stacked: empty state vs loaded state ─────────────────────────
        self._stack = FadingStack()

        # Page 0: empty state
        self._empty = _EmptyState()
        self._empty.files_dropped.connect(self._on_dropped)
        self._stack.addWidget(self._empty)

        # Page 1: loaded state
        self._loaded = self._build_loaded(settings)
        self._stack.addWidget(self._loaded)

        outer.addWidget(self._stack, 1)

    # ── loaded state builder ──────────────────────────────────────────────

    def _build_loaded(self, settings: CompressionSettings) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Stats bar
        self._stats_bar = _StatsBar()
        layout.addWidget(self._stats_bar)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.07); border: none;")
        layout.addWidget(sep)

        # Main row: queue + controls
        main_row = QHBoxLayout()
        main_row.setSpacing(16)
        main_row.setContentsMargins(0, 0, 0, 0)

        # Left: queue + add-more + action bar
        left = QVBoxLayout()
        left.setSpacing(10)
        left.setContentsMargins(0, 0, 0, 0)

        self._queue_widget = QueueWidget()
        self._queue_widget.clear_requested.connect(self.reset_queue)
        self._queue_widget.row_selected.connect(self._on_row_selected)
        left.addWidget(self._queue_widget, 1)

        # Before/After split view — shown when a job is selected
        self._split_card = QFrame()
        self._split_card.setObjectName("surfaceFlat")
        self._split_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sc_l = QVBoxLayout(self._split_card)
        sc_l.setContentsMargins(12, 10, 12, 10)
        sc_l.setSpacing(6)

        split_header = QHBoxLayout()
        split_title = QLabel("Before / After")
        split_title.setObjectName("h3")
        self._split_info = QLabel("Click a completed file to compare")
        self._split_info.setObjectName("dim")
        split_header.addWidget(split_title)
        split_header.addStretch(1)
        split_header.addWidget(self._split_info)
        sc_l.addLayout(split_header)

        self._split_view = SplitView()
        self._split_view.setFixedHeight(220)
        sc_l.addWidget(self._split_view)
        self._split_card.setVisible(False)
        left.addWidget(self._split_card)

        # Add-more compact drop
        self._compact_drop = DropZone(compact=True)
        self._compact_drop.files_dropped.connect(self._on_dropped)
        left.addWidget(self._compact_drop)

        # Action bar
        action_bar = QFrame()
        action_bar.setObjectName("surfaceFlat")
        action_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ab = QHBoxLayout(action_bar)
        ab.setContentsMargins(14, 10, 14, 10)
        ab.setSpacing(8)

        self._out_label = QLabel(self._fmt_out())
        self._out_label.setObjectName("dim")
        self._out_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._dir_btn = QPushButton("Output folder")
        self._dir_btn.setProperty("variant", "ghost")
        self._dir_btn.setFixedHeight(30)
        self._dir_btn.clicked.connect(self._on_choose_dir)

        self._reset_btn = QPushButton("Use source folder")
        self._reset_btn.setProperty("variant", "ghost")
        self._reset_btn.setFixedHeight(30)
        self._reset_btn.clicked.connect(self._on_reset_dir)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("variant", "danger")
        self._cancel_btn.setFixedHeight(30)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)

        self._zip_btn = QPushButton("Export ZIP")
        self._zip_btn.setProperty("variant", "ghost")
        self._zip_btn.setFixedHeight(30)
        self._zip_btn.setEnabled(False)
        self._zip_btn.clicked.connect(self.download_all_requested.emit)

        self._run_btn = QPushButton("Compress all")
        self._run_btn.setProperty("variant", "primary")
        self._run_btn.setFixedHeight(34)
        self._run_btn.setMinimumWidth(120)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self.run_requested.emit)

        ab.addWidget(self._out_label, 1)
        ab.addWidget(self._reset_btn)
        ab.addWidget(self._dir_btn)
        ab.addWidget(self._zip_btn)
        ab.addWidget(self._cancel_btn)
        ab.addWidget(self._run_btn)
        left.addWidget(action_bar)

        # Right: controls in a scroll area
        ctrl_scroll = QScrollArea()
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setFrameShape(QFrame.Shape.NoFrame)
        ctrl_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        ctrl_scroll.setFixedWidth(320)

        self.controls = ControlsPanel(settings)
        self.controls.settings_changed.connect(self.settings_changed.emit)
        ctrl_scroll.setWidget(self.controls)

        main_row.addLayout(left, 1)
        main_row.addWidget(ctrl_scroll, 0)
        layout.addLayout(main_row, 1)

        return w

    # ── public API ────────────────────────────────────────────────────────

    def set_settings(self, s: CompressionSettings) -> None:
        self._output_dir = s.output_dir
        self.controls.set_settings(s)
        self._out_label.setText(self._fmt_out())

    def queue(self) -> List[Path]:
        return list(self._sources)

    def has_jobs(self) -> bool:
        return bool(self._sources)

    def reset_queue(self) -> None:
        self._sources.clear()
        self._sizes.clear()
        self._queue_widget.reset()
        self._stack.setCurrentIndex(0)
        self._run_btn.setEnabled(False)
        self._zip_btn.setEnabled(False)
        self._split_card.setVisible(False)
        self._split_view.clear()
        self._stats_bar.update(
            completed=0, total=0, saved_bytes=0, reduction_pct=0.0
        )

    def populate_jobs(self, sources: List[Path]) -> None:
        deduped: list[Path] = []
        seen: set[Path] = set()
        for p in sources:
            try:
                rp = Path(p).resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if rp not in seen:
                seen.add(rp)
                deduped.append(rp)

        self._sources = deduped
        self._sizes = []
        for p in deduped:
            try:
                self._sizes.append(p.stat().st_size)
            except OSError:
                self._sizes.append(0)

        self._queue_widget.populate(self._sources, self._sizes)
        has = bool(self._sources)
        self._stack.setCurrentIndex(1 if has else 0)
        if has:
            fade_in(self._loaded, duration=180)
        self._run_btn.setEnabled(has)
        self._stats_bar.update(
            completed=0, total=len(self._sources),
            saved_bytes=0, reduction_pct=0.0,
        )

    def update_job(self, index: int, job: ImageJob) -> None:
        self._queue_widget.update_job(index, job)
        # Auto-show split view for the first completed job
        if job.status.value == "done" and job.output_path and job.output_path.exists():
            if not self._split_card.isVisible():
                self._split_card.setVisible(True)
                fade_in(self._split_card, duration=200)
            self._show_split(job)

    def _on_row_selected(self, job: ImageJob) -> None:
        """Called when the user clicks a queue row."""
        if job.status.value == "done" and job.output_path and job.output_path.exists():
            self._show_split(job)

    def _show_split(self, job: ImageJob) -> None:
        from PySide6.QtGui import QPixmap
        before_px = QPixmap(str(job.source))
        after_px  = QPixmap(str(job.output_path))
        if not before_px.isNull():
            self._split_view.set_before(before_px, "Original")
        if not after_px.isNull():
            savings = job.savings_percent
            self._split_view.set_after(
                after_px,
                f"Compressed  −{savings:.0f}%",
            )
        self._split_info.setText(job.source.name)

    def update_stats(
        self, *, completed: int, total: int,
        saved_bytes: int, reduction_pct: float
    ) -> None:
        self._stats_bar.update(
            completed=completed, total=total,
            saved_bytes=saved_bytes, reduction_pct=reduction_pct,
        )

    def set_running(self, running: bool) -> None:
        self._run_btn.setVisible(not running)
        self._cancel_btn.setVisible(running)
        self._dir_btn.setEnabled(not running)
        self._reset_btn.setEnabled(not running)

    def enable_zip(self, enabled: bool) -> None:
        """Called by MainWindow when at least one job finishes."""
        self._zip_btn.setEnabled(enabled)

    def open_files(self) -> None:
        """Ctrl+O shortcut — open file browser."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select images", str(Path.home()),
            "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff)",
        )
        if files:
            self._on_dropped([Path(f) for f in files])

    # ── internal ──────────────────────────────────────────────────────────

    def _on_dropped(self, raw: list) -> None:
        expanded = list(iter_image_paths(Path(p) for p in raw))
        if not expanded:
            return
        merged = list(self._sources) + [
            p for p in expanded if p not in self._sources
        ]
        self.populate_jobs(merged)
        self.files_added.emit(expanded)

    def _on_choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Choose output folder", str(Path.home())
        )
        if d:
            self._output_dir = Path(d)
            self._out_label.setText(self._fmt_out())
            self.output_dir_changed.emit(self._output_dir)

    def _on_reset_dir(self) -> None:
        self._output_dir = None
        self._out_label.setText(self._fmt_out())
        self.output_dir_changed.emit(None)

    def _fmt_out(self) -> str:
        if self._output_dir is None:
            return "Output: next to source files"
        return f"Output: {self._output_dir}"
