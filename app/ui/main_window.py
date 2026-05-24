"""Main application window — frameless, rounded corners, Qt-native resize/drag.

Architecture decision:
  We do NOT use nativeEvent / WM_NCHITTEST at all.
  Reason: nativeEvent intercepts ALL mouse events in the zones it claims,
  which breaks Qt button clicks and causes the "snap on hover" annoyance.

  Instead:
    • Title bar drag  → TitleBar.mouseMoveEvent  (pure Qt, 100% reliable)
    • Window resize   → MainWindow.mouseMoveEvent on the border strip
    • Rounded corners → _RoundedContainer.paintEvent + setMask
    • Snap to screen  → Works automatically when you drag to screen edges
                        because Qt moves the window via move(), and Windows
                        detects the position and offers snap on release.
"""

from __future__ import annotations

import enum
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QByteArray, QPoint, QRect, QSettings, Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QKeySequence,
    QPainter,
    QPainterPath,
    QRegion,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME
from ..models import CompressionSettings, ImageJob, JobStatus, Preset
from ..theme import build_stylesheet, get_theme, set_theme
from ..workers import BatchController
from .animated import FadingStack
from .dashboard import DashboardPage
from .feature_pages import ExifPage, GifPage, PdfPage, ResizerPage, WatermarkPage
from .pages import AboutPage, PresetsPage, SettingsPage
from .removebg_page import RemoveBgPage
from .converter_page import ConverterPage
from .workflow_pages import (
    ColourPalettePage, DashboardStatsPage, FolderWatchPage,
    HistoryPage, MetadataCleanerPage, OutputNamingPage,
)
from .sidebar import Sidebar
from .titlebar import TitleBar
from .toast import ToastManager

_BORDER = 6    # resize grip thickness in px
_RADIUS = 10   # corner radius in px


class _Edge(enum.IntFlag):
    NONE   = 0
    LEFT   = 1
    RIGHT  = 2
    TOP    = 4
    BOTTOM = 8


def _fmt(n: int) -> str:
    if n <= 0:
        return "0 B"
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} {u}"
        n /= 1024
    return f"{n:.1f} TB"


class _RoundedContainer(QWidget):
    """Central widget — paints the rounded background and clips children."""

    _BG_DARK  = QColor("#1a1a1a")
    _BG_LIGHT = QColor("#fafafa")

    def __init__(self, radius: int, bg: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = radius
        self._bg = QColor(bg)
        self._is_maximized = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setObjectName("root")

    def set_theme(self, theme: str) -> None:
        self._bg = self._BG_LIGHT if theme == "light" else self._BG_DARK
        self.update()

    def set_maximized(self, maximized: bool) -> None:
        """Remove the rounded mask when maximized so edges are fully usable."""
        self._is_maximized = maximized
        if maximized:
            self.clearMask()
        else:
            self._apply_mask()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        # No rounding when maximized — fill the full rectangle
        if self._is_maximized:
            path.addRect(0.0, 0.0, float(self.width()), float(self.height()))
        else:
            path.addRoundedRect(0.0, 0.0,
                                float(self.width()), float(self.height()),
                                self._radius, self._radius)
        p.fillPath(path, self._bg)
        p.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Only apply the rounded mask when NOT maximized
        if not self._is_maximized:
            self._apply_mask()

    def _apply_mask(self) -> None:
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0,
                            float(self.width()), float(self.height()),
                            self._radius, self._radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(960, 640)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Resize state
        self._resize_edge = _Edge.NONE
        self._resize_start_pos: QPoint | None = None
        self._resize_start_geo: QRect | None = None
        self.setMouseTracking(True)

        self._theme = get_theme()
        self._settings = CompressionSettings()
        self._batch = BatchController(self)
        self._toasts = ToastManager(self)

        # ── Rounded container ─────────────────────────────────────────────
        bg_color = "#fafafa" if self._theme == "light" else "#1a1a1a"
        self._container = _RoundedContainer(_RADIUS, bg_color)
        root_vbox = QVBoxLayout(self._container)
        root_vbox.setContentsMargins(0, 0, 0, 0)
        root_vbox.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────
        self._sidebar = Sidebar()
        self._sidebar.nav_changed.connect(self._on_nav)
        self._sidebar.select("dashboard")
        self._sidebar.set_theme(self._theme)   # apply saved theme on startup

        # ── Title bar ─────────────────────────────────────────────────────
        self._titlebar = TitleBar()
        self._titlebar.set_window(self)
        self._titlebar.set_theme(self._theme)
        self._titlebar.close_clicked.connect(self.close)
        self._titlebar.min_clicked.connect(self.showMinimized)
        self._titlebar.max_clicked.connect(self._toggle_max)
        self._titlebar.sidebar_toggle.connect(self._sidebar.toggle)
        root_vbox.addWidget(self._titlebar)

        # ── Body ──────────────────────────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._sidebar, 0)

        self._pages = FadingStack()
        self._dashboard      = DashboardPage(self._settings)
        self._removebg_page  = RemoveBgPage()
        self._converter_page = ConverterPage()
        self._resizer_page   = ResizerPage()
        self._watermark_page = WatermarkPage()
        self._exif_page      = ExifPage()
        self._gif_page       = GifPage()
        self._pdf_page       = PdfPage()
        self._palette_page   = ColourPalettePage()
        self._metaclean_page = MetadataCleanerPage()
        self._watch_page     = FolderWatchPage()
        self._naming_page    = OutputNamingPage()
        self._history_page   = HistoryPage()
        self._stats_page     = DashboardStatsPage()
        self._presets_page   = PresetsPage()
        self._settings_page  = SettingsPage(current_theme=self._theme)
        self._about_page     = AboutPage()

        self._dashboard.settings_changed.connect(self._on_settings_changed)
        self._dashboard.run_requested.connect(self._on_run)
        self._dashboard.cancel_requested.connect(self._batch.cancel)
        self._dashboard.output_dir_changed.connect(self._on_output_dir)
        self._dashboard.download_all_requested.connect(self._on_download_all)
        self._presets_page.preset_chosen.connect(self._on_preset)
        self._settings_page.theme_changed.connect(self._on_theme_changed)
        self._watch_page.compress_requested.connect(self._on_watch_compress)

        # Page index map
        self._page_map = {
            "dashboard": 0,  "removebg": 1,   "converter": 2,
            "resizer":   3,  "watermark": 4,  "exif": 5,
            "gif":       6,  "pdf": 7,        "palette": 8,
            "metaclean": 9,  "watch": 10,     "naming": 11,
            "history":   12, "stats": 13,     "presets": 14,
            "settings":  15, "about": 16,
        }
        for page in [
            self._dashboard, self._removebg_page, self._converter_page,
            self._resizer_page, self._watermark_page, self._exif_page,
            self._gif_page, self._pdf_page, self._palette_page,
            self._metaclean_page, self._watch_page, self._naming_page,
            self._history_page, self._stats_page, self._presets_page,
            self._settings_page, self._about_page,
        ]:
            self._pages.addWidget(page)

        body.addWidget(self._pages, 1)
        root_vbox.addLayout(body, 1)
        self.setCentralWidget(self._container)

        # Batch wiring
        self._batch.job_finished.connect(self._on_job_finished)
        self._batch.job_started.connect(self._on_job_started)
        self._batch.progress.connect(self._on_progress)
        self._batch.all_finished.connect(self._on_batch_done)

        self._done = 0
        self._total = 0
        self._saved = 0
        self._orig_total = 0
        self._completed_jobs: List[ImageJob] = []

        self._install_shortcuts()
        self._restore_geometry()

    # ── Qt-native resize (no nativeEvent, no WM_NCHITTEST) ───────────────
    # We handle resize entirely in Qt mouse events on the main window.
    # This means:
    #   • No Windows API interference with button clicks
    #   • Works identically on all platforms
    #   • No "snap on hover" because we only start resizing on mouse-DOWN

    def _edge_at(self, pos: QPoint) -> _Edge:
        """Return which resize edge(s) the cursor is on, or NONE."""
        if self.isMaximized() or self.isFullScreen():
            return _Edge.NONE
        b = _BORDER
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        edge = _Edge.NONE
        if x <= b:
            edge |= _Edge.LEFT
        if x >= w - b:
            edge |= _Edge.RIGHT
        if y <= b:
            edge |= _Edge.TOP
        if y >= h - b:
            edge |= _Edge.BOTTOM
        return edge

    def _cursor_for_edge(self, edge: _Edge) -> Qt.CursorShape:
        if edge in (_Edge.LEFT, _Edge.RIGHT):
            return Qt.CursorShape.SizeHorCursor
        if edge in (_Edge.TOP, _Edge.BOTTOM):
            return Qt.CursorShape.SizeVerCursor
        if edge in (_Edge.TOP | _Edge.LEFT, _Edge.BOTTOM | _Edge.RIGHT):
            return Qt.CursorShape.SizeFDiagCursor
        if edge in (_Edge.TOP | _Edge.RIGHT, _Edge.BOTTOM | _Edge.LEFT):
            return Qt.CursorShape.SizeBDiagCursor
        return Qt.CursorShape.ArrowCursor

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._edge_at(event.position().toPoint())
            if edge != _Edge.NONE:
                self._resize_edge = edge
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geo = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()

        # If actively resizing, apply the delta
        if (self._resize_edge != _Edge.NONE
                and self._resize_start_pos is not None
                and self._resize_start_geo is not None
                and event.buttons() & Qt.MouseButton.LeftButton):

            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            min_w, min_h = self.minimumWidth(), self.minimumHeight()

            if self._resize_edge & _Edge.LEFT:
                new_left = geo.left() + delta.x()
                if geo.right() - new_left >= min_w:
                    geo.setLeft(new_left)
            if self._resize_edge & _Edge.RIGHT:
                new_right = geo.right() + delta.x()
                if new_right - geo.left() >= min_w:
                    geo.setRight(new_right)
            if self._resize_edge & _Edge.TOP:
                new_top = geo.top() + delta.y()
                if geo.bottom() - new_top >= min_h:
                    geo.setTop(new_top)
            if self._resize_edge & _Edge.BOTTOM:
                new_bottom = geo.bottom() + delta.y()
                if new_bottom - geo.top() >= min_h:
                    geo.setBottom(new_bottom)

            self.setGeometry(geo)
            event.accept()
            return

        # Not resizing — just update the cursor shape
        edge = self._edge_at(pos)
        if edge != _Edge.NONE:
            self.setCursor(self._cursor_for_edge(edge))
        else:
            self.unsetCursor()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._resize_edge = _Edge.NONE
            self._resize_start_pos = None
            self._resize_start_geo = None
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if self._resize_edge == _Edge.NONE:
            self.unsetCursor()
        super().leaveEvent(event)

    # ── window controls ───────────────────────────────────────────────────

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event) -> None:
        """React to window state changes (maximize / restore / minimize)."""
        super().changeEvent(event)
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            maximized = self.isMaximized()
            # Update the □/❐ button symbol
            self._titlebar.update_max_button(maximized)
            # Remove rounded mask when maximized so scrollbars and
            # content at the screen edges are fully accessible.
            self._container.set_maximized(maximized)

    # ── geometry persistence ──────────────────────────────────────────────

    def _restore_geometry(self) -> None:
        s = QSettings("Mistix", "Compressly")
        geom: QByteArray = s.value("geometry", QByteArray())
        if geom and not geom.isEmpty():
            self.restoreGeometry(geom)
        else:
            self.resize(1280, 820)
            screen = QApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                self.move(
                    sg.center().x() - self.width() // 2,
                    sg.center().y() - self.height() // 2,
                )

    def _save_geometry(self) -> None:
        QSettings("Mistix", "Compressly").setValue("geometry", self.saveGeometry())

    # ── shortcuts ─────────────────────────────────────────────────────────

    def _install_shortcuts(self) -> None:
        for seq, slot in (
            ("Ctrl+Return",  self._on_run),
            ("Esc",          self._batch.cancel),
            ("Ctrl+O",       self._dashboard.open_files),
            ("Ctrl+Shift+Z", self._on_download_all),
            ("Ctrl+\\",      self._sidebar.toggle),
            ("Ctrl+V",       self._paste_clipboard),
        ):
            a = QAction(self)
            a.setShortcut(QKeySequence(seq))
            a.triggered.connect(slot)
            self.addAction(a)

    def _paste_clipboard(self) -> None:
        """Ctrl+V — paste an image from the clipboard into the queue."""
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasImage():
            import tempfile
            from pathlib import Path as _P
            img = clipboard.image()
            if not img.isNull():
                tmp = tempfile.mktemp(suffix=".png", prefix="compressly_clip_")
                img.save(tmp, "PNG")
                self._dashboard._on_dropped([_P(tmp)])
                self._toasts.show("Pasted image from clipboard", level="info")
        elif mime.hasUrls():
            paths = [Path(u.toLocalFile()) for u in mime.urls()
                     if Path(u.toLocalFile()).suffix.lower()
                     in {".jpg",".jpeg",".png",".webp",".bmp",".gif",".tiff"}]
            if paths:
                self._dashboard._on_dropped(paths)

    def _on_watch_compress(self, path: Path, _settings) -> None:
        """Auto-compress a file detected by folder watch."""
        from ..engine import compress_image
        settings = self._settings
        out_dir = path.parent / "_compressed"
        out_dir.mkdir(exist_ok=True)
        settings_with_dir = settings.with_output_dir(out_dir)
        try:
            compress_image(path, settings_with_dir)
            self._toasts.show(f"Auto-compressed: {path.name}", level="success")
        except Exception as exc:
            self._toasts.show(f"Watch error: {exc}", level="error")

    # ── navigation ────────────────────────────────────────────────────────

    def _on_nav(self, key: str) -> None:
        self._pages.setCurrentIndex(self._page_map.get(key, 0))
        # Refresh live pages when navigated to
        if key == "history":
            self._history_page.refresh()
        elif key == "stats":
            self._stats_page.refresh()

    # ── settings ──────────────────────────────────────────────────────────

    def _on_settings_changed(self, s: CompressionSettings) -> None:
        self._settings = s

    def _on_output_dir(self, d: Optional[Path]) -> None:
        self._settings = replace(self._settings, output_dir=d)
        self._dashboard.set_settings(self._settings)

    def _on_preset(self, preset: Preset) -> None:
        self._settings = preset.apply(self._settings)
        self._dashboard.set_settings(self._settings)
        self._sidebar.select("dashboard")
        self._on_nav("dashboard")
        self._toasts.show(f"Applied: {preset.name}", level="info")

    def _on_theme_changed(self, theme: str) -> None:
        self._theme = theme
        set_theme(theme)
        self._sidebar.set_theme(theme)
        self._container.set_theme(theme)
        self._titlebar.set_theme(theme)
        QApplication.instance().setStyleSheet(build_stylesheet(theme))

    # ── batch ─────────────────────────────────────────────────────────────

    def _on_run(self) -> None:
        if self._batch.is_running:
            return
        sources: List[Path] = self._dashboard.queue()
        if not sources:
            self._toasts.show("Add some images first.", level="info")
            return
        self._done = 0
        self._total = len(sources)
        self._saved = 0
        self._orig_total = 0
        self._completed_jobs = []
        self._dashboard.set_running(True)
        self._titlebar.set_status_running()
        if self._batch.submit(sources, self._settings) == 0:
            self._dashboard.set_running(False)
            self._titlebar.set_status_idle()

    def _on_job_started(self, index: int) -> None:
        q = self._dashboard.queue()
        if index < len(q):
            job = ImageJob(source=q[index], settings=self._settings)
            job.status = JobStatus.RUNNING
            self._dashboard.update_job(index, job)

    def _on_job_finished(self, index: int, job: ImageJob) -> None:
        self._dashboard.update_job(index, job)
        if job.status is JobStatus.DONE:
            self._saved += job.savings_bytes
            self._orig_total += job.original_size
            self._completed_jobs.append(job)
            self._dashboard.enable_zip(True)
            # Log to history
            try:
                from ..core.history import log_entry
                log_entry(
                    filename=job.source.name,
                    original_size=job.original_size,
                    compressed_size=job.output_size,
                    output_format=job.settings.output_format.value,
                    quality=job.settings.quality,
                    source_path=str(job.source),
                    output_path=str(job.output_path) if job.output_path else "",
                )
            except Exception:
                pass

    def _on_progress(self, completed: int, total: int) -> None:
        self._done = completed
        pct = (self._saved / self._orig_total * 100) if self._orig_total > 0 else 0.0
        self._dashboard.update_stats(
            completed=completed, total=total,
            saved_bytes=self._saved, reduction_pct=pct,
        )

    def _on_batch_done(self) -> None:
        self._dashboard.set_running(False)
        if self._total:
            self._titlebar.set_status_done(
                f"{self._done}/{self._total} · saved {_fmt(self._saved)}"
            )
            self._toasts.show(
                f"Done — {self._done}/{self._total} files, saved {_fmt(self._saved)}",
                level="success",
            )
        else:
            self._titlebar.set_status_idle()

    # ── ZIP download ──────────────────────────────────────────────────────

    def _on_download_all(self) -> None:
        done_jobs = [j for j in self._completed_jobs
                     if j.output_path and j.output_path.exists()]
        if not done_jobs:
            self._toasts.show("No compressed files to export yet.", level="info")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export all as ZIP",
            str(Path.home() / "compressly_export.zip"),
            "ZIP Archive (*.zip)",
        )
        if not dest:
            return
        try:
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                for job in done_jobs:
                    zf.write(str(job.output_path), job.output_path.name)
            self._toasts.show(
                f"Exported {len(done_jobs)} files to ZIP.", level="success"
            )
        except OSError as exc:
            self._toasts.show(f"Export failed: {exc}", level="error")

    # ── shutdown ──────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._batch.is_running:
            self._batch.cancel()
            self._batch.wait_for_done(2000)
        self._save_geometry()
        super().closeEvent(event)
