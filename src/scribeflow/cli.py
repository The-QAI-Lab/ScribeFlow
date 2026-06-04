"""ScribeFlow CLI."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from scribeflow import __version__
from scribeflow.config import LEDGER_PATH, REQUIRED_DIRECTORIES
from scribeflow.enhancer import EnhancementOptions, enhance_transcript
from scribeflow.exporter import export_markdown
from scribeflow.indexer import (
    SearchIndexError,
    index_completed_transcripts,
    search_index,
)
from scribeflow.ledger import Ledger
from scribeflow.media import extract_audio, normalized_audio_path
from scribeflow.scanner import scan_workspace
from scribeflow.status import load_status
from scribeflow.transcriber import transcribe_audio, write_transcript_json
from scribeflow.utils import ensure_directories, normalize_filename, to_relative_posix

app = typer.Typer(help="Local-first CLI for MP3/MP4 transcript tracking.")
console = Console()
FAILED_STATUSES = ("failed_audio", "failed_transcription", "failed_export")


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
        None, "--limit", min=1, help="Process only N pending files."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help="Process one tracked file by original filename or source path.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be processed without changes."
    ),
    model: str = typer.Option("small", "--model", help="faster-whisper model name."),
    language: str | None = typer.Option(
        None, "--language", help="Optional language hint, for example 'en'."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show detailed FFmpeg/STT errors where available."
    ),
    enhance: bool = typer.Option(
        False, "--enhance", help="Enable all deterministic study enhancements."
    ),
    summary_enabled: bool = typer.Option(
        False, "--summary", help="Generate summary bullets."
    ),
    terms: bool = typer.Option(False, "--terms", help="Extract key terms."),
    questions: bool = typer.Option(
        False, "--questions", help="Generate study questions."
    ),
    notes: bool = typer.Option(False, "--notes", help="Generate study notes."),
) -> None:
    """Process pending files into WAV, raw JSON, and Markdown transcripts."""
    root = Path(".")
    ensure_directories(root, REQUIRED_DIRECTORIES)
    ledger = Ledger(root / LEDGER_PATH)
    ledger.initialize()
    rows = ledger.pending_entries(limit=limit, file_selector=file)

    if dry_run:
        process_summary = _empty_process_summary(len(rows))
        failures: list[tuple[str, str, str]] = []
        _print_process_summary(process_summary, failures, dry_run=True, rows=rows)
        return

    process_summary, failures = _run_process_pipeline(
        root=root,
        ledger=ledger,
        rows=rows,
        model=model,
        language=language,
        verbose=verbose,
        enhancement_options=EnhancementOptions.from_flags(
            enhance=enhance,
            summary=summary_enabled,
            notes=notes,
            terms=terms,
            questions=questions,
        ),
    )
    _print_process_summary(process_summary, failures, dry_run=False, rows=rows)


@app.command()
def retry(
    limit: int | None = typer.Option(
        None, "--limit", min=1, help="Retry only N failed files."
    ),
    model: str = typer.Option("small", "--model", help="faster-whisper model name."),
    language: str | None = typer.Option(
        None, "--language", help="Optional language hint, for example 'en'."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show detailed FFmpeg/STT errors where available."
    ),
) -> None:
    """Retry jobs that failed during audio, transcription, or export."""
    root = Path(".")
    ensure_directories(root, REQUIRED_DIRECTORIES)
    ledger = Ledger(root / LEDGER_PATH)
    ledger.initialize()
    rows = ledger.entries_by_status(FAILED_STATUSES, limit=limit)
    ledger.reset_to_pending([int(row["id"]) for row in rows])

    summary, failures = _run_process_pipeline(
        root=root,
        ledger=ledger,
        rows=rows,
        model=model,
        language=language,
        verbose=verbose,
    )
    _print_process_summary(
        summary,
        failures,
        dry_run=False,
        rows=rows,
        title="ScribeFlow Retry Summary",
    )


@app.command()
def reprocess(
    file: str = typer.Option(
        ..., "--file", help="Tracked original filename or source path to reprocess."
    ),
    model: str = typer.Option("small", "--model", help="faster-whisper model name."),
    language: str | None = typer.Option(
        None, "--language", help="Optional language hint, for example 'en'."
    ),
    force: bool = typer.Option(
        False, "--force", help="Explicitly overwrite existing generated outputs."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show detailed FFmpeg/STT errors where available."
    ),
    enhance: bool = typer.Option(
        False, "--enhance", help="Enable all deterministic study enhancements."
    ),
    summary_enabled: bool = typer.Option(
        False, "--summary", help="Generate summary bullets."
    ),
    terms: bool = typer.Option(False, "--terms", help="Extract key terms."),
    questions: bool = typer.Option(
        False, "--questions", help="Generate study questions."
    ),
    notes: bool = typer.Option(False, "--notes", help="Generate study notes."),
) -> None:
    """Regenerate WAV, JSON, and Markdown for a tracked file."""
    _ = force
    root = Path(".")
    ensure_directories(root, REQUIRED_DIRECTORIES)
    ledger = Ledger(root / LEDGER_PATH)
    ledger.initialize()
    row = ledger.get_by_selector(file)
    if row is None:
        console.print(f"[red]No tracked file found for:[/red] {file}")
        raise typer.Exit(code=1)

    ledger.reset_to_pending([int(row["id"])])
    refreshed = ledger.get_by_selector(file)
    rows = [refreshed if refreshed is not None else row]
    summary, failures = _run_process_pipeline(
        root=root,
        ledger=ledger,
        rows=rows,
        model=model,
        language=language,
        verbose=verbose,
        enhancement_options=EnhancementOptions.from_flags(
            enhance=enhance,
            summary=summary_enabled,
            notes=notes,
            terms=terms,
            questions=questions,
        ),
    )
    _print_process_summary(
        summary,
        failures,
        dry_run=False,
        rows=rows,
        title="ScribeFlow Reprocess Summary",
    )


@app.command()
def clean(
    audio: bool = typer.Option(False, "--audio", help="Clean working/audio files."),
    temp: bool = typer.Option(False, "--temp", help="Clean working/temp files."),
    logs: bool = typer.Option(False, "--logs", help="Clean working/logs files."),
    all: bool = typer.Option(False, "--all", help="Clean audio, temp, and logs."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show files that would be removed."
    ),
) -> None:
    """Remove generated working files without touching source media or ledger."""
    root = Path(".")
    targets: list[Path] = []
    if all or audio:
        targets.append(root / "working/audio")
    if all or temp:
        targets.append(root / "working/temp")
    if all or logs:
        targets.append(root / "working/logs")

    if not targets:
        console.print("[yellow]No clean target selected. Use --audio, --temp, --logs, or --all.[/yellow]")
        raise typer.Exit(code=1)

    files = _generated_files_for_clean(targets)
    removed = 0
    if not dry_run:
        for file_path in files:
            file_path.unlink()
            removed += 1

    table = Table(title="ScribeFlow Clean Summary")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Files selected", str(len(files)))
    table.add_row("Files removed", str(removed))
    table.add_row("Dry run", "yes" if dry_run else "no")
    console.print(table)

    if dry_run and files:
        selected = Table(title="Clean Dry Run")
        selected.add_column("File")
        for file_path in files:
            selected.add_row(file_path.as_posix())
        console.print(selected)


@app.command()
def archive(
    failed: bool = typer.Option(
        False, "--failed", help="Also move failed source media to archive/failed."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show moves without changing files or ledger."
    ),
) -> None:
    """Archive completed source media and optionally failed source media."""
    root = Path(".")
    ensure_directories(root, REQUIRED_DIRECTORIES)
    ledger = Ledger(root / LEDGER_PATH)
    ledger.initialize()
    rows = ledger.entries_by_status(("completed",))
    if failed:
        rows.extend(ledger.entries_by_status(FAILED_STATUSES))

    moved = 0
    failures: list[tuple[str, str, str]] = []
    planned: list[tuple[str, str]] = []
    for row in rows:
        source_path = root / str(row["source_path"])
        filename = str(row["original_filename"])
        destination_root = (
            root / "archive/failed"
            if str(row["status"]).startswith("failed_")
            else root / "archive/completed"
        )
        destination = _archive_destination(
            destination_root, source_path.name, str(row["file_hash"])
        )
        planned.append((source_path.as_posix(), destination.as_posix()))

        if dry_run:
            continue
        if not source_path.exists():
            failures.append((filename, "archive", "source file not found"))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination))
        ledger.update_source_path(
            int(row["id"]), to_relative_posix(destination, root)
        )
        moved += 1

    table = Table(title="ScribeFlow Archive Summary")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Files selected", str(len(rows)))
    table.add_row("Files moved", str(moved))
    table.add_row("Failed moves", str(len(failures)))
    table.add_row("Dry run", "yes" if dry_run else "no")
    console.print(table)

    if dry_run and planned:
        move_table = Table(title="Archive Dry Run")
        move_table.add_column("From")
        move_table.add_column("To")
        for source, destination in planned:
            move_table.add_row(source, destination)
        console.print(move_table)

    if failures:
        failure_table = Table(title="Archive Failures")
        failure_table.add_column("Filename")
        failure_table.add_column("Stage")
        failure_table.add_column("Error")
        for filename, stage, error in failures:
            failure_table.add_row(filename, stage, error)
        console.print(failure_table)


@app.command("index")
def index_command(
    rebuild: bool = typer.Option(
        False, "--rebuild", help="Delete and recreate the local search index."
    ),
    include_markdown: bool = typer.Option(
        False,
        "--include-markdown",
        help="Also index Summary, Study Notes, Key Terms, and Study Questions.",
    ),
) -> None:
    """Build or update the local transcript search index."""
    root = Path(".")
    ensure_directories(root, REQUIRED_DIRECTORIES)
    try:
        summary = index_completed_transcripts(
            root,
            rebuild=rebuild,
            include_markdown=include_markdown,
        )
    except SearchIndexError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="ScribeFlow Index Summary")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Transcript files seen", str(summary.files_seen))
    table.add_row("Transcript files indexed", str(summary.files_indexed))
    table.add_row("Transcript segments indexed", str(summary.transcript_segments_indexed))
    table.add_row("Markdown sections indexed", str(summary.markdown_sections_indexed))
    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(10, "--limit", min=1, help="Maximum results."),
    source: str | None = typer.Option(
        None, "--source", help="Filter by source filename/path substring."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print machine-readable JSON results."
    ),
) -> None:
    """Search indexed transcript segments and optional Markdown sections."""
    try:
        results = search_index(Path("."), query, limit=limit, source=source)
    except SearchIndexError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        console.print_json(json=json.dumps([result.to_dict() for result in results]))
        return

    table = Table(title="ScribeFlow Search Results")
    table.add_column("Source")
    table.add_column("Time")
    table.add_column("Match")
    table.add_column("Markdown")
    for result in results:
        table.add_row(
            result.source_file,
            result.timestamp,
            result.snippet,
            result.markdown_path or "-",
        )
    if not results:
        table.add_row("-", "-", "No matches found.", "-")
    console.print(table)


def _empty_process_summary(selected: int) -> dict[str, int]:
    return {
        "selected": selected,
        "audio": 0,
        "transcribed": 0,
        "markdown": 0,
        "completed": 0,
    }


def _run_process_pipeline(
    *,
    root: Path,
    ledger: Ledger,
    rows: list[dict[str, str | int | None]],
    model: str,
    language: str | None,
    verbose: bool,
    enhancement_options: EnhancementOptions | None = None,
) -> tuple[dict[str, int], list[tuple[str, str, str]]]:
    summary = _empty_process_summary(len(rows))
    failures: list[tuple[str, str, str]] = []

    for row in rows:
        filename = str(row["original_filename"])
        entry_id = int(row["id"])
        source_path = root / str(row["source_path"])
        file_hash = str(row["file_hash"])
        safe_stem = Path(normalize_filename(filename)).stem
        json_path = root / "output/raw_json" / f"{safe_stem}.json"
        markdown_path = root / "output/markdown" / f"{safe_stem}.md"
        audio_path = normalized_audio_path(root, filename, file_hash)
        started_at = datetime.now(UTC).isoformat()
        processed_at = datetime.now()

        ledger.mark_started(entry_id, started_at)

        try:
            extract_audio(source_path, audio_path, verbose=verbose)
            ledger.update_status(
                entry_id,
                "audio_extracted",
                output_audio_path=audio_path.as_posix(),
                error_message=None,
            )
            summary["audio"] += 1
        except Exception as exc:
            _mark_failure(ledger, entry_id, "failed_audio", exc, failures, filename)
            continue

        try:
            transcript = transcribe_audio(
                audio_path,
                source_file=str(row["source_path"]),
                model=model,
                language=language,
            )
            write_transcript_json(transcript, json_path)
            ledger.update_status(
                entry_id,
                "transcribed",
                output_json_path=json_path.as_posix(),
                error_message=None,
            )
            summary["transcribed"] += 1
        except Exception as exc:
            _mark_failure(
                ledger, entry_id, "failed_transcription", exc, failures, filename
            )
            continue

        try:
            enhancements = (
                enhance_transcript(transcript, enhancement_options)
                if enhancement_options and enhancement_options.any_enabled()
                else None
            )
            export_markdown(
                transcript,
                markdown_path,
                title=Path(filename).stem.replace("_", " ").replace("-", " ").title(),
                source_filename=filename,
                media_type=str(row["file_type"]),
                processed_at=processed_at,
                model=model,
                enhancements=enhancements,
            )
            ledger.update_status(
                entry_id,
                "markdown_exported",
                output_markdown_path=markdown_path.as_posix(),
                error_message=None,
            )
            summary["markdown"] += 1
        except Exception as exc:
            _mark_failure(ledger, entry_id, "failed_export", exc, failures, filename)
            continue

        if markdown_path.exists():
            ledger.update_status(
                entry_id,
                "completed",
                completed_at=datetime.now(UTC).isoformat(),
                error_message=None,
            )
            summary["completed"] += 1

    return summary, failures


def _short_error(error: Exception) -> str:
    message = str(error).strip()
    return message.splitlines()[0][:180] if message else error.__class__.__name__


def _mark_failure(
    ledger: Ledger,
    entry_id: int,
    status: str,
    error: Exception,
    failures: list[tuple[str, str, str]],
    filename: str,
) -> None:
    short_error = _short_error(error)
    ledger.update_status(
        entry_id,
        status,
        error_message=short_error,
        increment_retry=True,
    )
    failures.append((filename, status, short_error))


def _print_process_summary(
    summary: dict[str, int],
    failures: list[tuple[str, str, str]],
    *,
    dry_run: bool,
    rows: list[dict[str, str | int | None]],
    title: str = "ScribeFlow Process Summary",
) -> None:
    table = Table(title=title)
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Files selected", str(summary["selected"]))
    table.add_row("Audio extracted", str(summary["audio"]))
    table.add_row("Transcribed", str(summary["transcribed"]))
    table.add_row("Markdown exported", str(summary["markdown"]))
    table.add_row("Completed", str(summary["completed"]))
    table.add_row("Failed", str(len(failures)))
    console.print(table)

    if dry_run and rows:
        selected = Table(title="Dry Run Selection")
        selected.add_column("Filename")
        selected.add_column("Source")
        for row in rows:
            selected.add_row(str(row["original_filename"]), str(row["source_path"]))
        console.print(selected)

    if failures:
        failure_table = Table(title="Failures")
        failure_table.add_column("Filename")
        failure_table.add_column("Failed Stage")
        failure_table.add_column("Error")
        for filename, status, error in failures:
            failure_table.add_row(filename, status, error)
        console.print(failure_table)


def _generated_files_for_clean(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if not target.exists():
            continue
        for file_path in target.rglob("*"):
            if file_path.is_file() and file_path.name != ".gitkeep":
                files.append(file_path)
    return sorted(files)


def _archive_destination(archive_root: Path, filename: str, file_hash: str) -> Path:
    destination = archive_root / filename
    if not destination.exists():
        return destination

    source_name = Path(filename)
    suffix = file_hash[:8]
    candidate = archive_root / f"{source_name.stem}_{suffix}{source_name.suffix}"
    counter = 2
    while candidate.exists():
        candidate = archive_root / (
            f"{source_name.stem}_{suffix}_{counter}{source_name.suffix}"
        )
        counter += 1
    return candidate
