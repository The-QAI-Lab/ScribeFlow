from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scribeflow.exporter import export_markdown, format_timestamp


def test_markdown_timestamp_formatting() -> None:
    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(4.9) == "00:00:04"
    assert format_timestamp(3661.2) == "01:01:01"


def test_markdown_export_creates_expected_sections(tmp_path: Path) -> None:
    transcript = {
        "segments": [
            {"id": 0, "start": 0.0, "end": 4.2, "text": "Welcome."},
            {"id": 1, "start": 4.2, "end": 10.0, "text": "Today we learn."},
        ]
    }
    output_path = tmp_path / "lecture.md"

    export_markdown(
        transcript,
        output_path,
        title="Lecture Title",
        source_filename="test_lecture.mp3",
        media_type="mp3",
        processed_at=datetime(2026, 6, 4, 12, 30),
        model="small",
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "# Lecture Title" in markdown
    assert "**Source file:** test_lecture.mp3" in markdown
    assert "**Model:** faster-whisper-small" in markdown
    assert "## Summary" in markdown
    assert "## Timestamped Transcript" in markdown
    assert "### 00:00:00 - 00:00:04" in markdown
    assert "Welcome." in markdown
    assert "## Study Notes" in markdown
    assert "## Key Terms" in markdown
    assert "## Study Questions" in markdown


def test_markdown_export_includes_enhanced_sections_when_enabled(
    tmp_path: Path,
) -> None:
    transcript = {
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 4.2,
                "text": "Backpropagation updates model weights.",
            }
        ]
    }
    output_path = tmp_path / "enhanced.md"

    export_markdown(
        transcript,
        output_path,
        title="Enhanced Lecture",
        source_filename="lecture.mp3",
        media_type="mp3",
        processed_at=datetime(2026, 6, 4, 12, 30),
        model="small",
        enhancements={
            "summary": ["Backpropagation updates model weights."],
            "notes": ["Model weights are updated during training."],
            "terms": ["Backpropagation", "Model Weights"],
            "questions": ["What is Backpropagation?"],
        },
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "- Backpropagation updates model weights." in markdown
    assert "- Model weights are updated during training." in markdown
    assert "- Model Weights" in markdown
    assert "1. What is Backpropagation?" in markdown
    assert "## Timestamped Transcript" in markdown


def test_markdown_export_keeps_placeholders_when_enhancement_disabled(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "plain.md"

    export_markdown(
        {"segments": []},
        output_path,
        title="Plain Lecture",
        source_filename="lecture.mp3",
        media_type="mp3",
        processed_at=datetime(2026, 6, 4, 12, 30),
        model="small",
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "Summary generation is not implemented yet." in markdown
    assert "Study note generation is not implemented yet." in markdown
    assert "Key term extraction is not implemented yet." in markdown
    assert "Study question generation is not implemented yet." in markdown
