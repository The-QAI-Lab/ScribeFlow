"""Markdown transcript export."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


class ExportError(RuntimeError):
    """Raised when transcript export fails."""


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS."""
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def markdown_for_transcript(
    transcript: dict[str, Any],
    *,
    title: str,
    source_filename: str,
    media_type: str,
    processed_at: datetime,
    model: str,
    enhancements: dict[str, list[str]] | None = None,
) -> str:
    """Render transcript JSON as timestamped Markdown."""
    sections = enhancements or {}
    lines = [
        f"# {title}",
        "",
        f"**Source file:** {source_filename}  ",
        f"**Media type:** {media_type.upper()}  ",
        f"**Processed:** {processed_at.strftime('%Y-%m-%d %H:%M')}  ",
        f"**Model:** faster-whisper-{model}  ",
        "**Status:** Completed  ",
        "",
        "---",
        "",
        "## Summary",
        "",
        *_bullet_lines(
            sections.get("summary"),
            placeholder="Summary generation is not implemented yet.",
        ),
        "",
        "---",
        "",
        "## Study Notes",
        "",
        *_bullet_lines(
            sections.get("notes"),
            placeholder="Study note generation is not implemented yet.",
        ),
        "",
        "---",
        "",
        "## Key Terms",
        "",
        *_bullet_lines(
            sections.get("terms"),
            placeholder="Key term extraction is not implemented yet.",
        ),
        "",
        "---",
        "",
        "## Study Questions",
        "",
        *_numbered_lines(
            sections.get("questions"),
            placeholder="Study question generation is not implemented yet.",
        ),
        "",
        "---",
        "",
        "## Timestamped Transcript",
        "",
    ]

    for segment in transcript.get("segments", []):
        start = format_timestamp(float(segment["start"]))
        end = format_timestamp(float(segment["end"]))
        text = str(segment["text"]).strip()
        lines.extend([f"### {start} - {end}", text, ""])

    return "\n".join(lines)


def export_markdown(
    transcript: dict[str, Any],
    output_path: Path,
    *,
    title: str,
    source_filename: str,
    media_type: str,
    processed_at: datetime,
    model: str,
    enhancements: dict[str, list[str]] | None = None,
) -> Path:
    """Write timestamped Markdown transcript."""
    try:
        markdown = markdown_for_transcript(
            transcript,
            title=title,
            source_filename=source_filename,
            media_type=media_type,
            processed_at=processed_at,
            model=model,
            enhancements=enhancements,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except Exception as exc:
        raise ExportError(str(exc)) from exc
    return output_path


def _bullet_lines(items: list[str] | None, *, placeholder: str) -> list[str]:
    if not items:
        return [placeholder]
    return [f"- {item}" for item in items]


def _numbered_lines(items: list[str] | None, *, placeholder: str) -> list[str]:
    if not items:
        return [placeholder]
    return [f"{index}. {item}" for index, item in enumerate(items, start=1)]
