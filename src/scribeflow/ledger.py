"""SQLite ledger access layer."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


ALLOWED_STATUSES = (
    "pending",
    "audio_extracted",
    "failed_audio",
    "completed",
    "failed",
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
    output_markdown_path: str | None = None
    output_json_path: str | None = None
    output_subtitle_path: str | None = None
    output_audio_path: str | None = None
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
                    output_audio_path TEXT,
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

            table_sql_row = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'ledger'"
            ).fetchone()
            table_sql = str(table_sql_row[0] or "") if table_sql_row else ""
            if "audio_extracted" not in table_sql or "failed_audio" not in table_sql:
                self._migrate_ledger_schema(connection)

            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(ledger)").fetchall()
            }
            if "output_audio_path" not in columns:
                connection.execute("ALTER TABLE ledger ADD COLUMN output_audio_path TEXT")

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
                    SUM(CASE WHEN status = 'audio_extracted' THEN 1 ELSE 0 END) AS audio_extracted,
                    SUM(CASE WHEN status = 'failed_audio' THEN 1 ELSE 0 END) AS failed_audio,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
                FROM ledger
                """
            ).fetchone()

        return {
            "total": int(row[0] or 0),
            "pending": int(row[1] or 0),
            "audio_extracted": int(row[2] or 0),
            "failed_audio": int(row[3] or 0),
            "completed": int(row[4] or 0),
            "failed": int(row[5] or 0),
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

    def pending_for_processing(
        self, *, filename: str | None = None, limit: int | None = None
    ) -> list[dict[str, str | int]]:
        """Return pending rows for processing, optionally filtered."""
        query = """
            SELECT id, source_path, original_filename, normalized_filename, file_type, file_hash
            FROM ledger
            WHERE status = 'pending'
        """
        params: list[object] = []

        if filename:
            query += " AND original_filename = ?"
            params.append(Path(filename).name)

        query += " ORDER BY discovered_at ASC, id ASC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, params).fetchall()

        return [
            {
                "id": int(row["id"]),
                "source_path": str(row["source_path"]),
                "original_filename": str(row["original_filename"]),
                "normalized_filename": str(row["normalized_filename"]),
                "file_type": str(row["file_type"]),
                "file_hash": str(row["file_hash"]),
            }
            for row in rows
        ]

    def mark_audio_extracted(
        self, row_id: int, *, output_audio_path: str, completed_at: str
    ) -> None:
        """Mark a pending row as audio extracted and store output path."""
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE ledger
                SET
                    status = 'audio_extracted',
                    output_audio_path = ?,
                    completed_at = ?,
                    error_message = NULL
                WHERE id = ?
                """,
                (output_audio_path, completed_at, row_id),
            )

    def mark_audio_failed(self, row_id: int, *, error_message: str, completed_at: str) -> None:
        """Mark a pending row as failed during audio extraction."""
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE ledger
                SET
                    status = 'failed_audio',
                    output_audio_path = NULL,
                    completed_at = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (completed_at, error_message, row_id),
            )

    def _migrate_ledger_schema(self, connection: sqlite3.Connection) -> None:
        """Rebuild table schema when status constraints are outdated."""
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                normalized_filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_hash TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'audio_extracted', 'failed_audio', 'completed', 'failed')
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
        )

        existing_columns = [
            row[1] for row in connection.execute("PRAGMA table_info(ledger)").fetchall()
        ]
        target_columns = [
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
        shared_columns = [column for column in target_columns if column in existing_columns]

        unexpected_columns = [column for column in existing_columns if column not in target_columns]
        if unexpected_columns:
            raise RuntimeError(
                "Unexpected ledger schema mismatch during migration. "
                f"Unknown columns: {unexpected_columns}. "
                "Check for manual database edits or an incompatible ScribeFlow version."
            )

        if shared_columns:
            connection.row_factory = sqlite3.Row
            existing_rows = connection.execute("SELECT * FROM ledger").fetchall()

            insert_columns = ", ".join(target_columns)
            placeholders = ", ".join(["?"] * len(target_columns))
            for row in existing_rows:
                values = [row[column] if column in existing_columns else None for column in target_columns]
                connection.execute(
                    f"INSERT INTO ledger_new ({insert_columns}) VALUES ({placeholders})",
                    values,
                )

        connection.execute("DROP TABLE ledger")
        connection.execute("ALTER TABLE ledger_new RENAME TO ledger")
