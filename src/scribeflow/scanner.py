"""Inbox scanner implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scribeflow.config import INBOX_DIRECTORIES, LEDGER_PATH, SUPPORTED_EXTENSIONS
from scribeflow.hashing import sha256_file
from scribeflow.ledger import Ledger, LedgerEntry
from scribeflow.utils import normalize_filename, to_relative_posix


@dataclass(slots=True)
class ScanSummary:
    files_scanned: int = 0
    new_files_registered: int = 0
    duplicates_skipped: int = 0
    unsupported_files_ignored: int = 0


def scan_workspace(root: Path = Path(".")) -> ScanSummary:
    """Scan inbox folders and register new media files."""
    ledger = Ledger(root / LEDGER_PATH)
    ledger.initialize()

    summary = ScanSummary()

    for inbox in INBOX_DIRECTORIES:
        inbox_path = root / inbox
        if not inbox_path.exists():
            continue

        for file_path in sorted(inbox_path.iterdir()):
            if not file_path.is_file():
                continue

            summary.files_scanned += 1

            suffix = file_path.suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                summary.unsupported_files_ignored += 1
                continue

            file_hash = sha256_file(file_path)
            entry = LedgerEntry(
                source_path=to_relative_posix(file_path, root),
                original_filename=file_path.name,
                normalized_filename=normalize_filename(file_path.name),
                file_type=suffix.lstrip("."),
                file_size=file_path.stat().st_size,
                file_hash=file_hash,
                status="pending",
                discovered_at=datetime.now(UTC).isoformat(),
            )

            if ledger.register_pending(entry):
                summary.new_files_registered += 1
            else:
                summary.duplicates_skipped += 1

    return summary
