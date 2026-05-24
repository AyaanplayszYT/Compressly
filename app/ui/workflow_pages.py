"""Workflow & Analytics pages.

Pages:
  HistoryPage       — compression history log with lifetime stats
  FolderWatchPage   — folder watch mode
  OutputNamingPage  — custom output naming templates
  DashboardStatsPage— savings dashboard / lifetime analytics
  ColourPalettePage — extract dominant colours from an image
  MetadataCleanerPage — batch-strip metadata from a folder
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QProgressBar,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..core import history as hist
from ..core.folder_watch import FolderWatcher
from ..core.output_naming import TOKENS, DEFAULT_TEMPLATE, preview
from .helpers import format_bytes


def _surface() -> QFrame:
    f = QFrame()
    f.setObjectName("surface")
    f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return f

def _sep() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet("background-color: rgba(128,128,128,0.15);")
    return w

def _eyebrow(t: str) -> QLabel:
    l = QLabel(t); l.setObjectName("eyebrow"); return l

def _h1(t: str) -> QLabel:
    l = QLabel(t); l.setObjectName("h1"); return l

def _h3(t: str) -> QLabel:
    l = QLabel(t); l.setObjectName("h3"); return l

def _muted(t: str) -> QLabel:
    l = QLabel(t); l.setObjectName("muted"); l.setWordWrap(True); return l

def _page_wrap(inner: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(inner)
    return sa


# ── History Page ──────────────────────────────────────────────────────────────

class HistoryPage(QWidget):
    """Compression history log with lifetime stats and per-entry actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("HISTORY"))
        il.addWidget(_h1("Compression history"))
        il.addWidget(_muted("Every compression session is logged here. Click an entry to open the output file."))
        il.addWidget(_sep())

        # Stats row
        self._stats_card = _surface()
        sl = QHBoxLayout(self._stats_card)
        sl.setContentsMargins(18, 14, 18, 14)
        sl.setSpacing(0)
        self._stat_labels: dict[str, QLabel] = {}
        for key, label in (("total_files","Files"), ("total_saved","Saved"),
                            ("avg_savings_pct","Avg saving")):
            col = QVBoxLayout()
            col.setSpacing(2)
            v = QLabel("—")
            v.setObjectName("stat")
            v.setStyleSheet("font-size: 22px; font-weight: 700;")
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel(label.upper())
            lbl.setObjectName("eyebrow")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(v); col.addWidget(lbl)
            sl.addLayout(col, 1)
            self._stat_labels[key] = v
        il.addWidget(self._stats_card)

        # Actions
        act_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("variant", "ghost")
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self._load)
        clear_btn = QPushButton("Clear all")
        clear_btn.setProperty("variant", "danger")
        clear_btn.setFixedHeight(30)
        clear_btn.clicked.connect(self._clear_all)
        act_row.addStretch(1)
        act_row.addWidget(refresh_btn)
        act_row.addWidget(clear_btn)
        il.addLayout(act_row)

        # List
        self._list = QListWidget()
        self._list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        il.addWidget(self._list, 1)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)
        self._entries: List[hist.HistoryEntry] = []
        self._load()

    def _load(self) -> None:
        self._entries = hist.get_entries(200)
        self._list.clear()
        for e in self._entries:
            ts = datetime.fromtimestamp(e.timestamp).strftime("%Y-%m-%d %H:%M")
            text = (f"{e.filename}  ·  {format_bytes(e.original_size)} → "
                    f"{format_bytes(e.compressed_size)}  (−{e.savings_pct:.0f}%)  ·  {ts}")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, e.id)
            if not e.output_exists:
                item.setForeground(QColor(120, 120, 120))
            self._list.addItem(item)
        stats = hist.get_lifetime_stats()
        self._stat_labels["total_files"].setText(str(stats["total_files"]))
        self._stat_labels["total_saved"].setText(format_bytes(stats["total_saved"]))
        self._stat_labels["avg_savings_pct"].setText(f"{stats['avg_savings_pct']:.0f}%")

    def _on_double_click(self, item: QListWidgetItem) -> None:
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        entry = next((e for e in self._entries if e.id == entry_id), None)
        if entry and entry.output_exists:
            try:
                subprocess.run(["explorer", "/select,", entry.output_path], check=False)
            except OSError:
                pass

    def _clear_all(self) -> None:
        hist.clear_all()
        self._load()

    def refresh(self) -> None:
        self._load()


# ── Folder Watch Page ─────────────────────────────────────────────────────────

class FolderWatchPage(QWidget):
    """Pick a folder — any new image is auto-compressed to _compressed/."""

    compress_requested = Signal(object, object)  # Path, CompressionSettings

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._watcher = FolderWatcher(self)
        self._watcher.new_image.connect(self._on_new_image)
        self._watcher.status_changed.connect(self._on_status)
        self._processed: List[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("FOLDER WATCH"))
        il.addWidget(_h1("Auto-compress new images"))
        il.addWidget(_muted(
            "Pick a folder. Any image saved there is automatically compressed "
            "to a _compressed/ subfolder using your current settings."))
        il.addWidget(_sep())

        # Folder picker
        folder_card = _surface()
        fl = QVBoxLayout(folder_card)
        fl.setContentsMargins(16, 14, 16, 14)
        fl.setSpacing(10)

        folder_row = QHBoxLayout()
        self._folder_lbl = QLabel("No folder selected")
        self._folder_lbl.setObjectName("muted")
        self._folder_lbl.setSizePolicy(
            self._folder_lbl.sizePolicy().horizontalPolicy(),
            self._folder_lbl.sizePolicy().verticalPolicy())
        pick_btn = QPushButton("Choose folder")
        pick_btn.setFixedHeight(32)
        pick_btn.clicked.connect(self._pick_folder)
        folder_row.addWidget(self._folder_lbl, 1)
        folder_row.addWidget(pick_btn)
        fl.addLayout(folder_row)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start watching")
        self._start_btn.setProperty("variant", "primary")
        self._start_btn.setFixedHeight(34)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._toggle)
        self._status_lbl = QLabel("Idle")
        self._status_lbl.setObjectName("muted")
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._status_lbl, 1)
        fl.addLayout(btn_row)

        if not self._watcher.is_available:
            warn = QLabel("watchdog not installed — run: pip install watchdog")
            warn.setStyleSheet("color: #d07060;")
            fl.addWidget(warn)

        il.addWidget(folder_card)

        # Log
        log_card = _surface()
        ll = QVBoxLayout(log_card)
        ll.setContentsMargins(16, 14, 16, 14)
        ll.setSpacing(8)
        ll.addWidget(_h3("Activity log"))
        self._log = QListWidget()
        self._log.setMaximumHeight(200)
        self._log.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        ll.addWidget(self._log)
        il.addWidget(log_card)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)
        self._folder: Optional[Path] = None

    def _pick_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choose folder to watch", str(Path.home()))
        if d:
            self._folder = Path(d)
            self._folder_lbl.setText(str(self._folder))
            self._start_btn.setEnabled(True)

    def _toggle(self) -> None:
        if self._watcher.is_running:
            self._watcher.stop()
            self._start_btn.setText("Start watching")
            self._start_btn.setProperty("variant", "primary")
            self._start_btn.style().unpolish(self._start_btn)
            self._start_btn.style().polish(self._start_btn)
        else:
            if self._folder:
                self._watcher.start(self._folder)
                self._start_btn.setText("Stop watching")
                self._start_btn.setProperty("variant", "danger")
                self._start_btn.style().unpolish(self._start_btn)
                self._start_btn.style().polish(self._start_btn)

    def _on_new_image(self, path: Path) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.insertItem(0, f"[{ts}] New image: {path.name}")
        self._processed.append(str(path))
        self.compress_requested.emit(path, None)

    def _on_status(self, msg: str) -> None:
        self._status_lbl.setText(msg)


# ── Output Naming Page ────────────────────────────────────────────────────────

class OutputNamingPage(QWidget):
    """Custom output filename template editor."""

    template_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("OUTPUT NAMING"))
        il.addWidget(_h1("Custom filename templates"))
        il.addWidget(_muted("Use tokens to build dynamic output filenames. The template is applied to every compressed file."))
        il.addWidget(_sep())

        # Template input
        tmpl_card = _surface()
        tl = QVBoxLayout(tmpl_card)
        tl.setContentsMargins(16, 14, 16, 14)
        tl.setSpacing(10)
        tl.addWidget(_h3("Template"))

        self._tmpl_input = QLineEdit()
        self._tmpl_input.setText(DEFAULT_TEMPLATE)
        self._tmpl_input.setPlaceholderText("{name}_compressed")
        self._tmpl_input.textChanged.connect(self._on_changed)
        tl.addWidget(self._tmpl_input)

        self._preview_lbl = QLabel(f"Preview: {preview(DEFAULT_TEMPLATE)}.webp")
        self._preview_lbl.setObjectName("muted")
        tl.addWidget(self._preview_lbl)

        # Quick presets
        tl.addWidget(_h3("Quick templates"))
        presets_row = QHBoxLayout()
        presets_row.setSpacing(6)
        for tmpl in ("{name}_compressed", "{date}_{name}", "{name}_web",
                     "{width}x{height}_{name}", "{name}_v{n}"):
            b = QPushButton(tmpl)
            b.setObjectName("chip")
            b.setFixedHeight(28)
            b.clicked.connect(lambda _c, t=tmpl: self._apply_preset(t))
            presets_row.addWidget(b)
        presets_row.addStretch(1)
        tl.addLayout(presets_row)
        il.addWidget(tmpl_card)

        # Token reference
        ref_card = _surface()
        rl = QVBoxLayout(ref_card)
        rl.setContentsMargins(16, 14, 16, 14)
        rl.setSpacing(6)
        rl.addWidget(_h3("Available tokens"))
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)
        for row, (token, desc) in enumerate(TOKENS):
            t_lbl = QLabel(token)
            t_lbl.setStyleSheet("font-family: monospace; color: #d4956a;")
            d_lbl = QLabel(desc)
            d_lbl.setObjectName("muted")
            grid.addWidget(t_lbl, row, 0)
            grid.addWidget(d_lbl, row, 1)
        rl.addLayout(grid)
        il.addWidget(ref_card)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)

    def _on_changed(self, text: str) -> None:
        p = preview(text)
        self._preview_lbl.setText(f"Preview: {p}.webp")
        self.template_changed.emit(text)

    def _apply_preset(self, tmpl: str) -> None:
        self._tmpl_input.setText(tmpl)

    @property
    def template(self) -> str:
        return self._tmpl_input.text() or DEFAULT_TEMPLATE


# ── Savings Dashboard ─────────────────────────────────────────────────────────

class DashboardStatsPage(QWidget):
    """Lifetime savings analytics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("SAVINGS DASHBOARD"))
        il.addWidget(_h1("Your lifetime stats"))
        il.addWidget(_muted("Every compression you run is tracked here."))
        il.addWidget(_sep())

        # Big stats
        stats_card = _surface()
        sl = QGridLayout(stats_card)
        sl.setContentsMargins(20, 18, 20, 18)
        sl.setSpacing(16)
        self._big_stats: dict[str, QLabel] = {}
        items = [
            ("total_files",    "Files compressed",  "0"),
            ("total_saved",    "Total saved",        "0 B"),
            ("avg_savings_pct","Avg reduction",      "0%"),
            ("total_original", "Original total",     "0 B"),
        ]
        for i, (key, label, default) in enumerate(items):
            v = QLabel(default)
            v.setObjectName("stat")
            v.setStyleSheet("font-size: 28px; font-weight: 700;")
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel(label.upper())
            lbl.setObjectName("eyebrow")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col = QVBoxLayout()
            col.addWidget(v); col.addWidget(lbl)
            sl.addLayout(col, i // 2, i % 2)
            self._big_stats[key] = v
        il.addWidget(stats_card)

        refresh_btn = QPushButton("Refresh stats")
        refresh_btn.setProperty("variant", "ghost")
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self._load)
        il.addWidget(refresh_btn, 0, Qt.AlignmentFlag.AlignLeft)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)
        self._load()

    def _load(self) -> None:
        s = hist.get_lifetime_stats()
        self._big_stats["total_files"].setText(str(s["total_files"]))
        self._big_stats["total_saved"].setText(format_bytes(s["total_saved"]))
        self._big_stats["avg_savings_pct"].setText(f"{s['avg_savings_pct']:.1f}%")
        self._big_stats["total_original"].setText(format_bytes(s["total_original"]))

    def refresh(self) -> None:
        self._load()


# ── Colour Palette Extractor ──────────────────────────────────────────────────

class ColourPalettePage(QWidget):
    """Extract dominant colours from an image and display as swatches."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("COLOUR PALETTE"))
        il.addWidget(_h1("Extract dominant colours"))
        il.addWidget(_muted("Drop an image to extract its dominant colour palette. Click any swatch to copy the hex code."))
        il.addWidget(_sep())

        from .feature_pages import _DropZone
        drop = _DropZone("◉", "Drop an image to analyse")
        drop.file_dropped.connect(self._on_file)
        il.addWidget(drop)

        self._palette_card = _surface()
        self._palette_card.setVisible(False)
        pl = QVBoxLayout(self._palette_card)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(10)
        pl.addWidget(_h3("Dominant colours"))
        self._swatches_row = QHBoxLayout()
        self._swatches_row.setSpacing(8)
        pl.addLayout(self._swatches_row)
        self._copy_hint = QLabel("Click a swatch to copy its hex code")
        self._copy_hint.setObjectName("dim")
        pl.addWidget(self._copy_hint)
        il.addWidget(self._palette_card)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            self._on_file(Path(url.toLocalFile()))
            break

    def _on_file(self, path: Path) -> None:
        try:
            from PIL import Image
            with Image.open(path) as img:
                small = img.convert("RGB").resize((150, 150))
            quantized = small.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
            palette_data = quantized.getpalette()[:8*3]
            colours = [(palette_data[i], palette_data[i+1], palette_data[i+2])
                       for i in range(0, len(palette_data), 3)]
        except Exception as exc:
            self._copy_hint.setText(f"Error: {exc}")
            return

        # Clear old swatches
        while self._swatches_row.count():
            item = self._swatches_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from PySide6.QtWidgets import QApplication
        for r, g, b in colours:
            hex_code = f"#{r:02x}{g:02x}{b:02x}"
            swatch = QPushButton()
            swatch.setFixedSize(60, 60)
            swatch.setToolTip(f"Click to copy {hex_code}")
            swatch.setStyleSheet(
                f"background-color: {hex_code}; border-radius: 8px; border: none;"
            )
            swatch.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            swatch.clicked.connect(lambda _c, h=hex_code: (
                QApplication.clipboard().setText(h),
                self._copy_hint.setText(f"Copied {h}")
            ))
            self._swatches_row.addWidget(swatch)
        self._swatches_row.addStretch(1)
        self._palette_card.setVisible(True)


# ── Metadata Cleaner ──────────────────────────────────────────────────────────

class MetadataCleanerPage(QWidget):
    """Batch-strip all metadata from a folder of images."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folder: Optional[Path] = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(14)

        il.addWidget(_eyebrow("METADATA CLEANER"))
        il.addWidget(_h1("Strip metadata from images"))
        il.addWidget(_muted(
            "Remove EXIF, GPS, camera serial numbers, and software info from "
            "an entire folder of images. Outputs clean copies to a _clean/ subfolder."))
        il.addWidget(_sep())

        ctrl = _surface()
        cl = QVBoxLayout(ctrl)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        folder_row = QHBoxLayout()
        self._folder_lbl = QLabel("No folder selected")
        self._folder_lbl.setObjectName("muted")
        pick_btn = QPushButton("Choose folder")
        pick_btn.setFixedHeight(32)
        pick_btn.clicked.connect(self._pick)
        folder_row.addWidget(self._folder_lbl, 1)
        folder_row.addWidget(pick_btn)
        cl.addLayout(folder_row)

        self._clean_btn = QPushButton("Strip metadata from all images")
        self._clean_btn.setProperty("variant", "primary")
        self._clean_btn.setFixedHeight(34)
        self._clean_btn.setEnabled(False)
        self._clean_btn.clicked.connect(self._run)
        cl.addWidget(self._clean_btn)
        il.addWidget(ctrl)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        il.addWidget(self._progress)

        self._log = QListWidget()
        self._log.setMaximumHeight(200)
        self._log.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        il.addWidget(self._log)
        il.addStretch(1)

        outer.addWidget(_page_wrap(inner), 1)

    def _pick(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choose folder", str(Path.home()))
        if d:
            self._folder = Path(d)
            self._folder_lbl.setText(str(self._folder))
            self._clean_btn.setEnabled(True)

    def _run(self) -> None:
        if not self._folder:
            return
        exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
        files = [f for f in self._folder.iterdir()
                 if f.is_file() and f.suffix.lower() in exts]
        if not files:
            self._log.insertItem(0, "No images found in folder.")
            return

        out_dir = self._folder / "_clean"
        out_dir.mkdir(exist_ok=True)
        self._progress.setRange(0, len(files))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._log.clear()

        from PIL import Image, ImageOps
        done = 0
        for f in files:
            try:
                with Image.open(f) as img:
                    img = ImageOps.exif_transpose(img)
                    clean = img.copy()
                clean.save(str(out_dir / f.name))
                self._log.insertItem(0, f"Cleaned: {f.name}")
                done += 1
            except Exception as exc:
                self._log.insertItem(0, f"Error {f.name}: {exc}")
            self._progress.setValue(done)

        self._log.insertItem(0, f"Done — {done}/{len(files)} files cleaned to {out_dir}")
        self._progress.setVisible(False)
