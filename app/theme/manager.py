"""Persistent theme manager — saves/loads the user's theme choice."""

from __future__ import annotations

import json
from pathlib import Path

_PREFS_FILE = Path.home() / ".compressly" / "prefs.json"


def _load() -> dict:
    try:
        return json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PREFS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_theme() -> str:
    return _load().get("theme", "dark")


def set_theme(theme: str) -> None:
    data = _load()
    data["theme"] = theme
    _save(data)


def get_pref(key: str, default=None):
    return _load().get(key, default)


def set_pref(key: str, value) -> None:
    data = _load()
    data[key] = value
    _save(data)
