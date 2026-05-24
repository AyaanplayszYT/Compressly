"""Custom output naming — template system for output filenames.

Supported tokens:
  {name}    — original filename without extension
  {ext}     — output extension (webp, jpg, png)
  {date}    — YYYY-MM-DD
  {time}    — HHMMSS
  {n}       — sequential number (01, 02, …)
  {width}   — output width in pixels
  {height}  — output height in pixels
  {quality} — quality setting used
"""

from __future__ import annotations

import re
from datetime import datetime


_DEFAULT_TEMPLATE = "{name}_compressed"

_TOKENS = [
    ("{name}",    "Original filename without extension"),
    ("{ext}",     "Output format extension"),
    ("{date}",    "Date (YYYY-MM-DD)"),
    ("{time}",    "Time (HHMMSS)"),
    ("{n}",       "Sequential number (01, 02, …)"),
    ("{width}",   "Output width in pixels"),
    ("{height}",  "Output height in pixels"),
    ("{quality}", "Quality setting"),
]


def render(
    template: str,
    *,
    name: str,
    ext: str,
    n: int = 1,
    width: int = 0,
    height: int = 0,
    quality: int = 80,
) -> str:
    """Render a filename template to a concrete filename (without extension)."""
    now = datetime.now()
    result = template
    result = result.replace("{name}",    name)
    result = result.replace("{ext}",     ext.lstrip("."))
    result = result.replace("{date}",    now.strftime("%Y-%m-%d"))
    result = result.replace("{time}",    now.strftime("%H%M%S"))
    result = result.replace("{n}",       f"{n:02d}")
    result = result.replace("{width}",   str(width))
    result = result.replace("{height}",  str(height))
    result = result.replace("{quality}", str(quality))
    # Sanitise: remove characters that are invalid in Windows filenames
    result = re.sub(r'[<>:"/\\|?*]', "_", result)
    return result or name


def preview(template: str, name: str = "photo", ext: str = "webp") -> str:
    """Return a preview of what the template produces."""
    return render(template, name=name, ext=ext, n=1, width=1920, height=1080, quality=80)


TOKENS = _TOKENS
DEFAULT_TEMPLATE = _DEFAULT_TEMPLATE
