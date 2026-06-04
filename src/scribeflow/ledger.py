"""SQLite ledger access layer."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


ALLOWED_STATUSES = ("pending", "completed", "failed")


@dataclass(slots=True)
class LedgerEntry:
    source_path: str
    original_filename: str
    normalized_filename: str
    file_type: str
    file_size: int
    file_hash: str
    status: str = "pending"
    discovered_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    output_markdown_path: str | None = None
    output_json_path: str | None = None
    output_subtitle_path: str | None = None
    error_message: str | None = None
    retry_count: int = 0


class Ledger:
    """Provides read/write operations for the local ledger database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        """Create the ledger table and indexes if missing."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    normalized_filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
                    discovered_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    output_markdown_path TEXT,
                    output_json_path TEXT,
                    output_subtitle_path TEXT,
                    error_message TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_status ON ledger(status)"
            )

    def register_pending(self, entry: LedgerEntry) -> bool:
        """Insert a pending entry if hash is new; return True if inserted."""
        if entry.status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported status: {entry.status}")

        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO ledger (
                    source_path,
                    original_filename,
                    normalized_filename,
                    file_type,
                    file_size,
                    file_hash,
                    status,
                    discovered_at,
                    started_at,
                    completed_at,
                    output_markdown_path,
                    output_json_path,
                    output_subtitle_path,
                    error_message,
                    retry_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_hash) DO NOTHING
                """,
                (
                    entry.source_path,
                    entry.original_filename,
                    entry.normalized_filename,
                    entry.file_type,
                    entry.file_size,
                    entry.file_hash,
                    entry.status,
                    entry.discovered_at,
                    entry.started_at,
                    entry.completed_at,
                    entry.output_markdown_path,
                    entry.output_json_path,
                    entry.output_subtitle_path,
                    entry.error_message,
                    entry.retry_count,
                ),
            )
            return cursor.rowcount > 0

    def exists_by_hash(self, file_hash: str) -> bool:
        """Return True if a file hash is already tracked."""
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT 1 FROM ledger WHERE file_hash = ? LIMIT 1", (file_hash,)
            ).fetchone()
            return row is not None

    def counts(self) -> dict[str, int]:
        """Return total and per-status counts."""
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
                FROM ledger
                """
            ).fetchone()

        return {
            "total": int(row[0] or 0),
            "pending": int(row[1] or 0),
            "completed": int(row[2] or 0),
            "failed": int(row[3] or 0),
        }

    def pending_rows(self) -> list[dict[str, str | int]]:
        """Return pending files for status reporting."""
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT original_filename, file_type, file_size, discovered_at
                FROM ledger
                WHERE status = 'pending'
                ORDER BY discovered_at ASC
                """
            ).fetchall()

        return [
            {
                "original_filename": row["original_filename"],
                "file_type": row["file_type"],
                "file_size": int(row["file_size"]),
                "discovered_at": row["discovered_at"],
            }
            for row in rows
        ]
