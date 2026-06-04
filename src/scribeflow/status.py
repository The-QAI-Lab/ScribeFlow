"""Status query helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scribeflow.config import LEDGER_PATH
from scribeflow.ledger import Ledger


@dataclass(slots=True)
class StatusSnapshot:
    total: int
    pending: int
    audio_extracted: int
    failed_audio: int
    completed: int
    failed: int
    pending_files: list[dict[str, str | int]]


def load_status(root: Path = Path(".")) -> StatusSnapshot:
    """Load aggregate status and pending file details from ledger."""
    ledger = Ledger(root / LEDGER_PATH)
    ledger.initialize()

    counts = ledger.counts()
    pending_files = ledger.pending_rows()

    return StatusSnapshot(
        total=counts["total"],
        pending=counts["pending"],
        audio_extracted=counts["audio_extracted"],
        failed_audio=counts["failed_audio"],
        completed=counts["completed"],
        failed=counts["failed"],
        pending_files=pending_files,
    )
