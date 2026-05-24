"""Folder Watch Mode — auto-compress images dropped into a watched folder.

Uses watchdog to monitor a directory. Any new image file triggers
compression using the current settings. Output goes to a sibling
_compressed/ folder.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional, Set

from PySide6.QtCore import QObject, Signal

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False


SUPPORTED_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"})


class FolderWatcher(QObject):
    """Watch a folder and emit new_image_path when a supported image appears."""

    new_image = Signal(object)   # Path
    status_changed = Signal(str)  # status message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._observer: Optional[object] = None
        self._watched_path: Optional[Path] = None
        self._seen: Set[str] = set()
        self._lock = threading.Lock()

    @property
    def is_available(self) -> bool:
        return _WATCHDOG_AVAILABLE

    @property
    def is_running(self) -> bool:
        return self._observer is not None

    @property
    def watched_path(self) -> Optional[Path]:
        return self._watched_path

    def start(self, folder: Path) -> bool:
        if not _WATCHDOG_AVAILABLE:
            self.status_changed.emit("watchdog not installed — run: pip install watchdog")
            return False
        if self._observer is not None:
            self.stop()

        self._watched_path = folder
        self._seen.clear()

        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event: FileCreatedEvent) -> None:
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path.suffix.lower() not in SUPPORTED_EXTS:
                    return
                key = str(path)
                with watcher._lock:
                    if key in watcher._seen:
                        return
                    watcher._seen.add(key)
                watcher.new_image.emit(path)

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(folder), recursive=False)
        self._observer.start()
        self.status_changed.emit(f"Watching: {folder}")
        return True

    def stop(self) -> None:
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None
        self._watched_path = None
        self.status_changed.emit("Stopped")
