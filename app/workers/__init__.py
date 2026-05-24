"""Background workers (QThreadPool / QRunnable) for compression."""

from .batch import BatchController

__all__ = ["BatchController"]
