"""Threaded batch compression controller.

Uses QThreadPool + QRunnable. Each job runs on a worker thread; UI updates
arrive on the main thread via Qt signals.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Iterable, List, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ..engine import CompressionError, compress_image
from ..models import CompressionSettings, ImageJob, JobStatus


class _JobSignals(QObject):
    """Signals emitted by a single _JobRunnable."""

    started = Signal(int)              # job index
    finished = Signal(int, object)     # job index, ImageJob (updated copy)


class _JobRunnable(QRunnable):
    """Run one ImageJob on a worker thread."""

    def __init__(
        self,
        index: int,
        job: ImageJob,
        cancel_event: threading.Event,
        signals: _JobSignals,
    ) -> None:
        super().__init__()
        self._index = index
        self._job = job
        self._cancel = cancel_event
        self._signals = signals
        self.setAutoDelete(True)

    def _check_cancel(self) -> bool:
        return self._cancel.is_set()

    @Slot()
    def run(self) -> None:  # noqa: D401 - Qt convention
        if self._cancel.is_set():
            self._job.status = JobStatus.CANCELLED
            self._signals.finished.emit(self._index, self._job)
            return

        self._job.status = JobStatus.RUNNING
        self._signals.started.emit(self._index)

        try:
            result = compress_image(
                self._job.source,
                self._job.settings,
                cancel_check=self._check_cancel,
            )
            try:
                self._job.original_size = self._job.source.stat().st_size
            except OSError:
                self._job.original_size = 0
            self._job.output_path = result.output_path
            self._job.output_size = result.output_size
            self._job.output_width = result.width
            self._job.output_height = result.height
            self._job.duration_ms = result.duration_ms
            self._job.status = JobStatus.DONE
        except CompressionError as exc:
            msg = str(exc)
            if msg.lower() == "cancelled":
                self._job.status = JobStatus.CANCELLED
            else:
                self._job.status = JobStatus.ERROR
                self._job.error_message = msg
        except Exception as exc:  # last-resort safety net
            self._job.status = JobStatus.ERROR
            self._job.error_message = f"Unexpected error: {exc}"

        self._signals.finished.emit(self._index, self._job)


class BatchController(QObject):
    """Manage a queue of ImageJobs across a thread pool.

    Signals:
        job_started(int)                 — index in the active queue
        job_finished(int, ImageJob)      — index + updated job
        progress(int, int)               — completed, total
        all_finished()                   — emitted exactly once when the batch
                                            ends (success, errors, or cancel).
    """

    job_started = Signal(int)
    job_finished = Signal(int, object)
    progress = Signal(int, int)
    all_finished = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        # Cap thread count to keep memory bounded on big batches.
        cores = max(1, QThreadPool.globalInstance().maxThreadCount())
        self._pool.setMaxThreadCount(min(cores, 4))

        self._signals = _JobSignals()
        self._signals.started.connect(self._on_started)
        self._signals.finished.connect(self._on_finished)

        self._cancel = threading.Event()
        self._jobs: List[ImageJob] = []
        self._completed = 0
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def submit(self, sources: Iterable[Path], settings: CompressionSettings) -> int:
        """Queue a new batch. Returns the number of jobs scheduled."""
        if self._running:
            return 0

        self._jobs = [ImageJob(source=Path(p), settings=settings) for p in sources]
        if not self._jobs:
            self.all_finished.emit()
            return 0

        self._completed = 0
        self._cancel.clear()
        self._running = True

        for index, job in enumerate(self._jobs):
            runnable = _JobRunnable(index, job, self._cancel, self._signals)
            self._pool.start(runnable)

        self.progress.emit(0, len(self._jobs))
        return len(self._jobs)

    def cancel(self) -> None:
        """Request cancellation; in-flight jobs finish quickly via cancel_check."""
        if not self._running:
            return
        self._cancel.set()

    def wait_for_done(self, msec: int = -1) -> bool:
        """Block until all jobs finish. Used by tests / shutdown only."""
        if msec < 0:
            self._pool.waitForDone()
            return True
        return self._pool.waitForDone(msec)

    @Slot(int)
    def _on_started(self, index: int) -> None:
        self.job_started.emit(index)

    @Slot(int, object)
    def _on_finished(self, index: int, job: ImageJob) -> None:
        self._completed += 1
        # Replace the in-list job (it's the same object the runnable mutated,
        # but emit a defensive copy reference).
        self._jobs[index] = job
        self.job_finished.emit(index, job)
        self.progress.emit(self._completed, len(self._jobs))
        if self._completed >= len(self._jobs):
            self._running = False
            self.all_finished.emit()
