"""ScribeFlow CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from scribeflow import __version__
from scribeflow.config import LEDGER_PATH, REQUIRED_DIRECTORIES
from scribeflow.ledger import Ledger
from scribeflow.processor import process_pending
from scribeflow.scanner import scan_workspace
from scribeflow.status import load_status
from scribeflow.utils import ensure_directories

app = typer.Typer(help="Local-first CLI for MP3/MP4 transcript tracking.")
console = Console()


@app.command()
def version() -> None:
    """Print installed ScribeFlow version."""
    console.print(f"ScribeFlow {__version__}")


@app.command()
def init() -> None:
    """Initialize workspace directories and local ledger database."""
    root = Path(".")
    ensure_directories(root, REQUIRED_DIRECTORIES)

    ledger = Ledger(root / LEDGER_PATH)
    ledger.initialize()

    console.print("[green]Workspace ready.[/green]")
    console.print(f"Ledger: {(root / LEDGER_PATH).as_posix()}")


@app.command()
def scan() -> None:
    """Scan inbox folders and register new files."""
    summary = scan_workspace(Path("."))

    table = Table(title="Scan Summary")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Files scanned", str(summary.files_scanned))
    table.add_row("New files registered", str(summary.new_files_registered))
    table.add_row("Duplicates skipped", str(summary.duplicates_skipped))
    table.add_row("Unsupported files ignored", str(summary.unsupported_files_ignored))
    console.print(table)


@app.command()
def status() -> None:
    """Show ledger totals and pending files."""
    snapshot = load_status(Path("."))

    totals = Table(title="Ledger Status")
    totals.add_column("Metric")
    totals.add_column("Count", justify="right")
    totals.add_row("Total files tracked", str(snapshot.total))
    totals.add_row("Pending", str(snapshot.pending))
    totals.add_row("Audio extracted", str(snapshot.audio_extracted))
    totals.add_row("Failed audio", str(snapshot.failed_audio))
    totals.add_row("Completed", str(snapshot.completed))
    totals.add_row("Failed", str(snapshot.failed))
    console.print(totals)

    pending_table = Table(title="Pending Files")
    pending_table.add_column("Filename")
    pending_table.add_column("Type")
    pending_table.add_column("Size", justify="right")
    pending_table.add_column("Discovered At")

    if snapshot.pending_files:
        for row in snapshot.pending_files:
            pending_table.add_row(
                str(row["original_filename"]),
                str(row["file_type"]),
                str(row["file_size"]),
                str(row["discovered_at"]),
            )
    else:
        pending_table.add_row("-", "-", "-", "-")

    console.print(pending_table)


@app.command()
def process(
    limit: int | None = typer.Option(
        None,
        "--limit",
        min=1,
        help="Process at most this many pending files.",
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help="Process one pending file by original filename.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show processing selection without running FFmpeg or writing ledger updates.",
    ),
) -> None:
    """Process pending files into normalized WAV audio."""
    summary = process_pending(
        Path("."),
        limit=limit,
        filename=file,
        dry_run=dry_run,
    )

    table = Table(title="Process Summary")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Pending files in ledger", str(summary.discovered_pending))
    table.add_row("Selected for this run", str(summary.selected_for_run))
    table.add_row("Files processed", str(summary.processed))
    table.add_row("Audio extracted", str(summary.succeeded))
    table.add_row("Failed audio", str(summary.failed))
    table.add_row("Missing source files", str(summary.missing_source))
    table.add_row("Dry run", "yes" if summary.dry_run else "no")
    console.print(table)
