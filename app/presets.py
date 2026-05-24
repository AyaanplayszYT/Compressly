"""Built-in compression presets."""

from __future__ import annotations

from typing import List

from .models import OutputFormat, Preset, ResizeMode

PRESETS: List[Preset] = [
    Preset(
        key="ultra",
        name="Ultra Quality",
        description="Near-lossless WebP at 95%. Best for portfolios and print previews.",
        settings_overrides={
            "output_format": OutputFormat.WEBP,
            "quality": 95,
            "resize_mode": ResizeMode.NONE,
            "strip_metadata": False,
        },
    ),
    Preset(
        key="balanced",
        name="Balanced",
        description="Great quality at a much smaller size. Recommended default.",
        settings_overrides={
            "output_format": OutputFormat.WEBP,
            "quality": 82,
            "resize_mode": ResizeMode.NONE,
            "strip_metadata": True,
        },
    ),
    Preset(
        key="web",
        name="Web Optimized",
        description="Resize to 1920px wide and encode WebP at 78% — perfect for hero images.",
        settings_overrides={
            "output_format": OutputFormat.WEBP,
            "quality": 78,
            "resize_mode": ResizeMode.LONGEST,
            "resize_longest": 1920,
            "strip_metadata": True,
        },
    ),
    Preset(
        key="max",
        name="Maximum Compression",
        description="Aggressive WebP at 55%, downscaled 80%. Smallest possible files.",
        settings_overrides={
            "output_format": OutputFormat.WEBP,
            "quality": 55,
            "resize_mode": ResizeMode.PERCENT,
            "resize_percent": 80,
            "strip_metadata": True,
        },
    ),
]


def find_preset(key: str) -> Preset | None:
    for p in PRESETS:
        if p.key == key:
            return p
    return None
