"""SQLite ledger access layer."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


ALLOWED_STATUSES = (
    "pending",
    "audio_extracted",
    "transcribed",
    "markdown_exported",
    "completed",
    "failed_audio",
    "failed_transcription",
    "failed_export",
)


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
    output_audio_path: str | None = None
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
            self._ensure_schema(connection)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_status ON ledger(status)"
            )

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'ledger'"
        ).fetchone()
        if row is None:
            connection.execute(LEDGER_SCHEMA)
            return

        table_sql = str(row[0])
        columns = {
            column[1] for column in connection.execute("PRAGMA table_info(ledger)")
        }
        needs_rebuild = (
            "failed_audio" not in table_sql or "output_audio_path" not in columns
        )
        if not needs_rebuild:
            return

        connection.execute("ALTER TABLE ledger RENAME TO ledger_old")
        connection.execute(LEDGER_SCHEMA)
        old_columns = {
            column[1] for column in connection.execute("PRAGMA table_info(ledger_old)")
        }
        copied_columns = [
            column
            for column in LEDGER_COLUMNS
            if column in old_columns and column != "output_audio_path"
        ]
        select_columns = [
            (
                "CASE status "
                "WHEN 'failed' THEN 'failed_audio' "
                "WHEN 'pending' THEN 'pending' "
                "WHEN 'completed' THEN 'completed' "
                "ELSE status END AS status"
            )
            if column == "status"
            else column
            for column in copied_columns
        ]
        connection.execute(
            f"""
            INSERT INTO ledger ({", ".join(copied_columns)})
            SELECT {", ".join(select_columns)}
            FROM ledger_old
            """
        )
        connection.execute("DROP TABLE ledger_old")

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
                    output_audio_path,
                    output_markdown_path,
                    output_json_path,
                    output_subtitle_path,
                    error_message,
                    retry_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    entry.output_audio_path,
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
                    SUM(CASE WHEN status LIKE 'failed_%' THEN 1 ELSE 0 END) AS failed
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

    def entries_by_status(
        self,
        statuses: list[str] | tuple[str, ...],
        *,
        limit: int | None = None,
        file_selector: str | None = None,
    ) -> list[dict[str, str | int | None]]:
        """Return ledger rows matching one or more statuses."""
        if not statuses:
            return []
        for status in statuses:
            if status not in ALLOWED_STATUSES:
                raise ValueError(f"Unsupported status: {status}")

        placeholders = ", ".join("?" for _ in statuses)
        query = f"SELECT * FROM ledger WHERE status IN ({placeholders})"
        params: list[str | int] = list(statuses)
        if file_selector:
            query += " AND (original_filename = ? OR source_path = ?)"
            params.extend([file_selector, file_selector])
        query += " ORDER BY discovered_at ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, params).fetchall()

        return [dict(row) for row in rows]

    def pending_entries(
        self, limit: int | None = None, file_selector: str | None = None
    ) -> list[dict[str, str | int | None]]:
        """Return pending ledger rows selected for processing."""
        return self.entries_by_status(
            ("pending",), limit=limit, file_selector=file_selector
        )

    def get_by_selector(self, selector: str) -> dict[str, str | int | None] | None:
        """Return one ledger row by original filename or source path."""
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT * FROM ledger
                WHERE original_filename = ? OR source_path = ?
                LIMIT 1
                """,
                (selector, selector),
            ).fetchone()
        return dict(row) if row else None

    def get_by_filename(self, filename: str) -> dict[str, str | int | None] | None:
        """Return one ledger row by original filename."""
        return self.get_by_selector(filename)

    def mark_started(self, entry_id: int, started_at: str) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE ledger
                SET started_at = COALESCE(started_at, ?), error_message = NULL
                WHERE id = ?
                """,
                (started_at, entry_id),
            )

    def update_status(
        self,
        entry_id: int,
        status: str,
        *,
        output_audio_path: str | None = None,
        output_json_path: str | None = None,
        output_markdown_path: str | None = None,
        completed_at: str | None = None,
        error_message: str | None = None,
        increment_retry: bool = False,
    ) -> None:
        """Update processing status and artifact paths for a ledger row."""
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported status: {status}")

        assignments = ["status = ?"]
        params: list[str | int | None] = [status]
        for column, value in (
            ("output_audio_path", output_audio_path),
            ("output_json_path", output_json_path),
            ("output_markdown_path", output_markdown_path),
            ("completed_at", completed_at),
            ("error_message", error_message),
        ):
            if value is not None or column == "error_message":
                assignments.append(f"{column} = ?")
                params.append(value)
        if increment_retry:
            assignments.append("retry_count = retry_count + 1")
        params.append(entry_id)

        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                f"UPDATE ledger SET {', '.join(assignments)} WHERE id = ?",
                params,
            )

    def reset_to_pending(self, entry_ids: list[int]) -> None:
        """Reset selected rows to pending for retry/reprocess."""
        if not entry_ids:
            return
        placeholders = ", ".join("?" for _ in entry_ids)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                f"""
                UPDATE ledger
                SET status = 'pending',
                    started_at = NULL,
                    completed_at = NULL,
                    error_message = NULL
                WHERE id IN ({placeholders})
                """,
                entry_ids,
            )

    def update_source_path(self, entry_id: int, source_path: str) -> None:
        """Update a ledger row after archiving a source media file."""
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE ledger SET source_path = ? WHERE id = ?",
                (source_path, entry_id),
            )


LEDGER_COLUMNS = [
    "id",
    "source_path",
    "original_filename",
    "normalized_filename",
    "file_type",
    "file_size",
    "file_hash",
    "status",
    "discovered_at",
    "started_at",
    "completed_at",
    "output_audio_path",
    "output_markdown_path",
    "output_json_path",
    "output_subtitle_path",
    "error_message",
    "retry_count",
]


LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    normalized_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (
        status IN (
            'pending',
            'audio_extracted',
            'transcribed',
            'markdown_exported',
            'completed',
            'failed_audio',
            'failed_transcription',
            'failed_export'
        )
    ),
    discovered_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    output_audio_path TEXT,
    output_markdown_path TEXT,
    output_json_path TEXT,
    output_subtitle_path TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0
)
"""
