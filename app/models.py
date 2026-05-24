"""Typed data models used across the UI and engine layers."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Optional


class OutputFormat(str, Enum):
    """Supported output formats."""

    KEEP = "keep"
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"

    @property
    def display(self) -> str:
        return {
            OutputFormat.KEEP: "Keep original",
            OutputFormat.JPEG: "JPG",
            OutputFormat.PNG: "PNG",
            OutputFormat.WEBP: "WebP",
        }[self]

    @property
    def extension(self) -> str:
        """File extension WITHOUT a leading dot."""
        return {
            OutputFormat.KEEP: "",  # caller substitutes the source extension
            OutputFormat.JPEG: "jpg",
            OutputFormat.PNG: "png",
            OutputFormat.WEBP: "webp",
        }[self]


class ResizeMode(str, Enum):
    NONE = "none"
    PERCENT = "percent"
    LONGEST = "longest"  # constrain longest side to N pixels


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class CompressionSettings:
    """Settings applied uniformly to a batch of images."""

    output_format: OutputFormat = OutputFormat.WEBP
    quality: int = 80                # 1..100
    resize_mode: ResizeMode = ResizeMode.NONE
    resize_percent: int = 100        # 10..100, used when mode == PERCENT
    resize_longest: int = 1920       # >=64, used when mode == LONGEST
    keep_aspect_ratio: bool = True
    strip_metadata: bool = True
    output_dir: Optional[Path] = None  # None → write next to source as *_compressed
    overwrite: bool = False

    def with_output_dir(self, directory: Optional[Path]) -> "CompressionSettings":
        return replace(self, output_dir=directory)


@dataclass
class ImageJob:
    """A single image scheduled for compression."""

    source: Path
    settings: CompressionSettings
    status: JobStatus = JobStatus.QUEUED
    original_size: int = 0
    output_path: Optional[Path] = None
    output_size: int = 0
    width: int = 0
    height: int = 0
    output_width: int = 0
    output_height: int = 0
    error_message: Optional[str] = None
    duration_ms: int = 0

    @property
    def savings_bytes(self) -> int:
        if self.output_size <= 0 or self.original_size <= 0:
            return 0
        return max(0, self.original_size - self.output_size)

    @property
    def savings_percent(self) -> float:
        if self.output_size <= 0 or self.original_size <= 0:
            return 0.0
        return max(0.0, (1 - self.output_size / self.original_size) * 100.0)


@dataclass(frozen=True)
class Preset:
    """Built-in preset definition."""

    key: str
    name: str
    description: str
    settings_overrides: dict = field(default_factory=dict)

    def apply(self, base: CompressionSettings) -> CompressionSettings:
        return replace(base, **self.settings_overrides)
