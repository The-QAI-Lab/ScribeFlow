from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scribeflow.cli import app
from scribeflow.indexer import (
    SearchIndexError,
    create_search_schema,
    index_completed_transcripts,
    search_index,
)


runner = CliRunner()


def write_transcript(root: Path, name: str = "lecture") -> Path:
    raw_dir = root / "output/raw_json"
    markdown_dir = root / "output/markdown"
    raw_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)
    transcript = {
        "source_file": f"inbox/mp4/{name}.mp4",
        "audio_file": f"working/audio/{name}.wav",
        "model": "small",
        "language": "en",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 4.2,
                "text": "Backpropagation updates neural network weights.",
            },
            {
                "id": 1,
                "start": 4.2,
                "end": 8.0,
                "text": "The loss function measures prediction error.",
            },
        ],
    }
    json_path = raw_dir / f"{name}.json"
    json_path.write_text(json.dumps(transcript), encoding="utf-8")
    (markdown_dir / f"{name}.md").write_text(
        """
# Lecture

## Summary

- Neural networks learn from examples.

---

## Study Notes

- Gradient descent reduces loss.

---

## Key Terms

- Backpropagation

---

## Study Questions

1. What is backpropagation?

---

## Timestamped Transcript
""".strip(),
        encoding="utf-8",
    )
    return json_path


def test_search_index_database_is_created(tmp_path: Path) -> None:
    db_path = tmp_path / ".scribeflow/search.sqlite"

    create_search_schema(db_path)

    assert db_path.is_file()


def test_transcript_json_segments_are_indexed(tmp_path: Path) -> None:
    write_transcript(tmp_path)

    summary = index_completed_transcripts(tmp_path, rebuild=True)

    assert summary.files_seen == 1
    assert summary.files_indexed == 1
    assert summary.transcript_segments_indexed == 2


def test_search_returns_matching_segment_text(tmp_path: Path) -> None:
    write_transcript(tmp_path)
    index_completed_transcripts(tmp_path, rebuild=True)

    results = search_index(tmp_path, "backpropagation")

    assert results
    assert "Backpropagation updates" in results[0].snippet


def test_search_includes_timestamp_data(tmp_path: Path) -> None:
    write_transcript(tmp_path)
    index_completed_transcripts(tmp_path, rebuild=True)

    results = search_index(tmp_path, "loss")

    assert results[0].timestamp == "00:00:04 - 00:00:08"


def test_search_limit_works(tmp_path: Path) -> None:
    write_transcript(tmp_path, "one")
    write_transcript(tmp_path, "two")
    index_completed_transcripts(tmp_path, rebuild=True)

    results = search_index(tmp_path, "neural", limit=1)

    assert len(results) == 1


def test_rebuild_clears_old_index_data(tmp_path: Path) -> None:
    json_path = write_transcript(tmp_path)
    index_completed_transcripts(tmp_path, rebuild=True)
    json_path.unlink()

    summary = index_completed_transcripts(tmp_path, rebuild=True)

    assert summary.files_seen == 0
    assert search_index(tmp_path, "backpropagation") == []


def test_empty_query_is_handled_cleanly(tmp_path: Path) -> None:
    write_transcript(tmp_path)
    index_completed_transcripts(tmp_path, rebuild=True)

    with pytest.raises(SearchIndexError, match="cannot be empty"):
        search_index(tmp_path, "   ")


def test_missing_raw_json_folder_does_not_crash(tmp_path: Path) -> None:
    summary = index_completed_transcripts(tmp_path, rebuild=True)

    assert summary.files_seen == 0
    assert (tmp_path / ".scribeflow/search.sqlite").is_file()


def test_fts_unavailable_case_is_handled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_fts(*args, **kwargs):
        raise SearchIndexError("SQLite FTS5 is not available in this Python environment.")

    monkeypatch.setattr("scribeflow.indexer._ensure_fts5", fail_fts)

    with pytest.raises(SearchIndexError, match="FTS5"):
        index_completed_transcripts(tmp_path, rebuild=True)


def test_search_json_option_returns_machine_readable_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_transcript(tmp_path)
    index_completed_transcripts(tmp_path, rebuild=True)

    result = runner.invoke(app, ["search", "backpropagation", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload[0]["source_file"] == "inbox/mp4/lecture.mp4"
    assert payload[0]["timestamp"] == "00:00:00 - 00:00:04"


def test_index_include_markdown_indexes_study_sections(tmp_path: Path) -> None:
    write_transcript(tmp_path)

    summary = index_completed_transcripts(
        tmp_path, rebuild=True, include_markdown=True
    )
    results = search_index(tmp_path, "gradient")

    assert summary.markdown_sections_indexed == 4
    assert results[0].kind == "markdown"
