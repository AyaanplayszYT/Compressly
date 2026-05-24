"""Compression history — persisted to a local SQLite database.

Every compression job is logged with:
  filename, original_size, compressed_size, savings_pct,
  format, quality, timestamp, source_path, output_path
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List


_DB_PATH = Path.home() / ".compressly" / "history.db"


@dataclass
class HistoryEntry:
    id: int
    filename: str
    original_size: int
    compressed_size: int
    savings_pct: float
    output_format: str
    quality: int
    timestamp: float
    source_path: str
    output_path: str

    @property
    def savings_bytes(self) -> int:
        return max(0, self.original_size - self.compressed_size)

    @property
    def source_exists(self) -> bool:
        return Path(self.source_path).exists()

    @property
    def output_exists(self) -> bool:
        return Path(self.output_path).exists()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT NOT NULL,
            original_size INTEGER NOT NULL,
            compressed_size INTEGER NOT NULL,
            savings_pct   REAL NOT NULL,
            output_format TEXT NOT NULL,
            quality       INTEGER NOT NULL,
            timestamp     REAL NOT NULL,
            source_path   TEXT NOT NULL,
            output_path   TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def log_entry(
    filename: str,
    original_size: int,
    compressed_size: int,
    output_format: str,
    quality: int,
    source_path: str,
    output_path: str,
) -> None:
    savings_pct = max(0.0, (1 - compressed_size / original_size) * 100) if original_size else 0.0
    conn = _connect()
    conn.execute(
        "INSERT INTO history (filename, original_size, compressed_size, "
        "savings_pct, output_format, quality, timestamp, source_path, output_path) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (filename, original_size, compressed_size, savings_pct,
         output_format, quality, time.time(), source_path, output_path),
    )
    conn.commit()
    conn.close()


def get_entries(limit: int = 200) -> List[HistoryEntry]:
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT id, filename, original_size, compressed_size, savings_pct, "
            "output_format, quality, timestamp, source_path, output_path "
            "FROM history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [HistoryEntry(*row) for row in rows]
    except Exception:
        return []


def get_lifetime_stats() -> dict:
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT COUNT(*), SUM(original_size), SUM(compressed_size) FROM history"
        ).fetchone()
        conn.close()
        count, orig_total, comp_total = row
        count = count or 0
        orig_total = orig_total or 0
        comp_total = comp_total or 0
        saved = max(0, orig_total - comp_total)
        avg_pct = (saved / orig_total * 100) if orig_total > 0 else 0.0
        return {
            "total_files": count,
            "total_original": orig_total,
            "total_compressed": comp_total,
            "total_saved": saved,
            "avg_savings_pct": avg_pct,
        }
    except Exception:
        return {"total_files": 0, "total_original": 0,
                "total_compressed": 0, "total_saved": 0, "avg_savings_pct": 0.0}


def delete_entry(entry_id: int) -> None:
    try:
        conn = _connect()
        conn.execute("DELETE FROM history WHERE id = ?", (entry_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def clear_all() -> None:
    try:
        conn = _connect()
        conn.execute("DELETE FROM history")
        conn.commit()
        conn.close()
    except Exception:
        pass
