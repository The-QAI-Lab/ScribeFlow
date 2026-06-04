"""Audio processing for pending media files."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scribeflow.config import LEDGER_PATH
from scribeflow.ledger import Ledger


@dataclass(slots=True)
class ProcessSummary:
    discovered_pending: int = 0
    selected_for_run: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    missing_source: int = 0
    dry_run: bool = False


def _run_ffmpeg(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def process_pending(
    root: Path = Path("."),
    *,
    limit: int | None = None,
    filename: str | None = None,
    dry_run: bool = False,
) -> ProcessSummary:
    """Convert pending MP3/MP4 files to normalized WAV audio."""
    ledger = Ledger(root / LEDGER_PATH)
    ledger.initialize()

    summary = ProcessSummary(dry_run=dry_run)
    all_pending = ledger.pending_for_processing()
    summary.discovered_pending = len(all_pending)

    entries = ledger.pending_for_processing(filename=filename, limit=limit)
    summary.selected_for_run = len(entries)

    audio_dir = root / "working/audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        summary.processed += 1
        row_id = int(entry["id"])
        source_path = root / str(entry["source_path"])
        output_filename = _build_output_filename(
            str(entry["normalized_filename"]), str(entry["file_hash"])
        )
        output_path = audio_dir / output_filename
        output_relative = output_path.resolve().relative_to(root.resolve()).as_posix()

        if not source_path.exists():
            summary.failed += 1
            summary.missing_source += 1
            if not dry_run:
                ledger.mark_audio_failed(
                    row_id,
                    error_message=f"Source file is missing: {source_path.as_posix()}",
                    completed_at=datetime.now(UTC).isoformat(),
                )
            continue

        if dry_run:
            continue

        command = _ffmpeg_command(
            source_path=source_path,
            output_path=output_path,
            file_type=str(entry["file_type"]),
        )

        try:
            result = _run_ffmpeg(command)
        except FileNotFoundError:
            summary.failed += 1
            ledger.mark_audio_failed(
                row_id,
                error_message="ffmpeg executable not found on PATH",
                completed_at=datetime.now(UTC).isoformat(),
            )
            continue

        if result.returncode == 0 and output_path.exists():
            summary.succeeded += 1
            ledger.mark_audio_extracted(
                row_id,
                output_audio_path=output_relative,
                completed_at=datetime.now(UTC).isoformat(),
            )
            continue

        summary.failed += 1
        error_message = (result.stderr or "").strip() or (
            f"ffmpeg conversion failed with return code {result.returncode}"
        )
        ledger.mark_audio_failed(
            row_id,
            error_message=error_message,
            completed_at=datetime.now(UTC).isoformat(),
        )

    return summary


def _build_output_filename(normalized_filename: str, file_hash: str) -> str:
    stem = Path(normalized_filename).stem
    safe_stem = "".join(ch for ch in stem if ch.isalnum() or ch in {"-", "_"})
    safe_stem = safe_stem or "audio"
    return f"{safe_stem}_{file_hash[:12]}.wav"


def _ffmpeg_command(*, source_path: Path, output_path: Path, file_type: str) -> list[str]:
    command = ["ffmpeg", "-y", "-i", source_path.as_posix()]
    if file_type == "mp4":
        command.append("-vn")
    command.extend(["-ac", "1", "-ar", "16000", output_path.as_posix()])
    return command
