"""Local transcript indexing and search."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scribeflow.config import SEARCH_INDEX_PATH
from scribeflow.exporter import format_timestamp


class SearchIndexError(RuntimeError):
    """Raised when the local search index cannot be used."""


@dataclass(slots=True)
class IndexSummary:
    files_seen: int = 0
    files_indexed: int = 0
    transcript_segments_indexed: int = 0
    markdown_sections_indexed: int = 0


@dataclass(slots=True)
class SearchResult:
    source_file: str
    markdown_path: str
    json_path: str
    segment_id: int | None
    start_time: float | None
    end_time: float | None
    kind: str
    heading: str
    snippet: str

    @property
    def timestamp(self) -> str:
        if self.start_time is None or self.end_time is None:
            return "-"
        return f"{format_timestamp(self.start_time)} - {format_timestamp(self.end_time)}"

    def to_dict(self) -> dict[str, str | int | float | None]:
        return {
            "source_file": self.source_file,
            "timestamp": self.timestamp,
            "markdown_path": self.markdown_path,
            "json_path": self.json_path,
            "segment_id": self.segment_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "kind": self.kind,
            "heading": self.heading,
            "snippet": self.snippet,
        }


def create_search_schema(db_path: Path) -> None:
    """Create local FTS5 search index tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        _ensure_fts5(connection)
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                source_file UNINDEXED,
                markdown_path UNINDEXED,
                json_path UNINDEXED,
                segment_id UNINDEXED,
                start_time UNINDEXED,
                end_time UNINDEXED,
                kind,
                heading,
                text
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS indexed_files (
                json_path TEXT PRIMARY KEY,
                markdown_path TEXT,
                source_file TEXT,
                json_mtime REAL NOT NULL,
                markdown_mtime REAL,
                include_markdown INTEGER NOT NULL,
                indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def index_completed_transcripts(
    root: Path = Path("."),
    *,
    rebuild: bool = False,
    include_markdown: bool = False,
    db_path: Path | None = None,
) -> IndexSummary:
    """Index generated transcript JSON and optional Markdown sections."""
    index_path = db_path or root / SEARCH_INDEX_PATH
    raw_json_dir = root / "output/raw_json"
    markdown_dir = root / "output/markdown"

    if rebuild and index_path.exists():
        index_path.unlink()

    create_search_schema(index_path)
    summary = IndexSummary()
    if not raw_json_dir.exists():
        return summary

    with sqlite3.connect(index_path) as connection:
        _ensure_fts5(connection)
        for json_path in sorted(raw_json_dir.glob("*.json")):
            summary.files_seen += 1
            markdown_path = markdown_dir / f"{json_path.stem}.md"
            json_mtime = json_path.stat().st_mtime
            markdown_mtime = markdown_path.stat().st_mtime if markdown_path.exists() else None
            relative_json = _relative(json_path, root)
            relative_markdown = _relative(markdown_path, root) if markdown_path.exists() else ""

            row = connection.execute(
                "SELECT json_mtime, markdown_mtime, include_markdown FROM indexed_files WHERE json_path = ?",
                (relative_json,),
            ).fetchone()
            if (
                row
                and float(row[0]) == json_mtime
                and row[1] == markdown_mtime
                and int(row[2]) == int(include_markdown)
            ):
                continue

            _delete_indexed_file(connection, relative_json)
            transcript = _load_json(json_path)
            source_file = str(transcript.get("source_file") or json_path.name)
            summary.transcript_segments_indexed += index_transcript_json(
                connection,
                transcript,
                json_path=relative_json,
                markdown_path=relative_markdown,
                source_file=source_file,
            )
            if include_markdown and markdown_path.exists():
                summary.markdown_sections_indexed += index_markdown_sections(
                    connection,
                    markdown_path,
                    json_path=relative_json,
                    markdown_relative_path=relative_markdown,
                    source_file=source_file,
                )

            connection.execute(
                """
                INSERT OR REPLACE INTO indexed_files (
                    json_path, markdown_path, source_file, json_mtime,
                    markdown_mtime, include_markdown, indexed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    relative_json,
                    relative_markdown,
                    source_file,
                    json_mtime,
                    markdown_mtime,
                    int(include_markdown),
                ),
            )
            summary.files_indexed += 1

    return summary


def index_transcript_json(
    connection: sqlite3.Connection,
    transcript: dict[str, Any],
    *,
    json_path: str,
    markdown_path: str,
    source_file: str,
) -> int:
    """Index transcript segments from one raw JSON transcript."""
    count = 0
    for segment in transcript.get("segments", []):
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        connection.execute(
            """
            INSERT INTO search_fts (
                source_file, markdown_path, json_path, segment_id,
                start_time, end_time, kind, heading, text
            )
            VALUES (?, ?, ?, ?, ?, ?, 'transcript', 'Timestamped Transcript', ?)
            """,
            (
                source_file,
                markdown_path,
                json_path,
                int(segment.get("id", count)),
                float(segment.get("start", 0.0)),
                float(segment.get("end", 0.0)),
                text,
            ),
        )
        count += 1
    return count


def index_markdown_sections(
    connection: sqlite3.Connection,
    markdown_path: Path,
    *,
    json_path: str,
    markdown_relative_path: str,
    source_file: str,
) -> int:
    """Index study sections from an enhanced Markdown transcript."""
    sections = parse_markdown_sections(markdown_path.read_text(encoding="utf-8"))
    count = 0
    for heading in ("Summary", "Study Notes", "Key Terms", "Study Questions"):
        text = sections.get(heading, "").strip()
        if not text:
            continue
        connection.execute(
            """
            INSERT INTO search_fts (
                source_file, markdown_path, json_path, segment_id,
                start_time, end_time, kind, heading, text
            )
            VALUES (?, ?, ?, NULL, NULL, NULL, 'markdown', ?, ?)
            """,
            (source_file, markdown_relative_path, json_path, heading, text),
        )
        count += 1
    return count


def search_index(
    root: Path = Path("."),
    query: str = "",
    *,
    limit: int = 10,
    source: str | None = None,
    db_path: Path | None = None,
) -> list[SearchResult]:
    """Search the local FTS index."""
    fts_query = normalize_fts_query(query)
    index_path = db_path or root / SEARCH_INDEX_PATH
    if not index_path.exists():
        raise SearchIndexError("Search index not found. Run: scribeflow index")

    sql = """
        SELECT
            source_file,
            markdown_path,
            json_path,
            segment_id,
            start_time,
            end_time,
            kind,
            heading,
            snippet(search_fts, 8, '', '', '...', 18) AS snippet
        FROM search_fts
        WHERE search_fts MATCH ?
    """
    params: list[str | int] = [fts_query]
    if source:
        sql += " AND source_file LIKE ?"
        params.append(f"%{source}%")
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    try:
        with sqlite3.connect(index_path) as connection:
            connection.row_factory = sqlite3.Row
            _ensure_fts5(connection)
            rows = connection.execute(sql, params).fetchall()
    except sqlite3.OperationalError as exc:
        raise SearchIndexError(str(exc)) from exc

    return [
        SearchResult(
            source_file=str(row["source_file"]),
            markdown_path=str(row["markdown_path"]),
            json_path=str(row["json_path"]),
            segment_id=int(row["segment_id"]) if row["segment_id"] is not None else None,
            start_time=float(row["start_time"]) if row["start_time"] is not None else None,
            end_time=float(row["end_time"]) if row["end_time"] is not None else None,
            kind=str(row["kind"]),
            heading=str(row["heading"]),
            snippet=str(row["snippet"]),
        )
        for row in rows
    ]


def normalize_fts_query(query: str) -> str:
    """Convert user input into a simple safe FTS5 query."""
    tokens = re.findall(r"[A-Za-z0-9_]+", query)
    if not tokens:
        raise SearchIndexError("Search query cannot be empty.")
    return " ".join(tokens)


def parse_markdown_sections(markdown: str) -> dict[str, str]:
    """Extract second-level Markdown sections."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            continue
        if current and not line.startswith("---"):
            sections[current].append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}


def _delete_indexed_file(connection: sqlite3.Connection, json_path: str) -> None:
    connection.execute("DELETE FROM search_fts WHERE json_path = ?", (json_path,))
    connection.execute("DELETE FROM indexed_files WHERE json_path = ?", (json_path,))


def _ensure_fts5(connection: sqlite3.Connection) -> None:
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS fts5_probe USING fts5(value)"
        )
        connection.execute("DROP TABLE IF EXISTS fts5_probe")
    except sqlite3.OperationalError as exc:
        raise SearchIndexError(
            "SQLite FTS5 is not available in this Python environment."
        ) from exc


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
