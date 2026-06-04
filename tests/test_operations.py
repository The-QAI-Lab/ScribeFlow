from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from scribeflow.cli import app
from scribeflow.config import LEDGER_PATH
from scribeflow.ledger import Ledger


runner = CliRunner()


def write_file(path: Path, data: bytes = b"media") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def setup_tracked_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names: list[str]
) -> Ledger:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    for index, name in enumerate(names):
        folder = "mp4" if name.endswith(".mp4") else "mp3"
        write_file(tmp_path / f"inbox/{folder}/{name}", f"media-{index}".encode())
    runner.invoke(app, ["scan"])
    return Ledger(tmp_path / LEDGER_PATH)


def install_successful_pipeline_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_extract_audio(input_path: Path, output_path: Path, *, verbose: bool = False):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"wav")
        return output_path

    def fake_transcribe_audio(
        audio_path: Path,
        *,
        source_file: str,
        model: str = "small",
        language: str | None = None,
    ):
        return {
            "source_file": source_file,
            "audio_file": audio_path.as_posix(),
            "model": model,
            "language": language,
            "segments": [
                {"id": 0, "start": 0.0, "end": 2.0, "text": "Retry works."}
            ],
        }

    monkeypatch.setattr("scribeflow.cli.extract_audio", fake_extract_audio)
    monkeypatch.setattr("scribeflow.cli.transcribe_audio", fake_transcribe_audio)


def mark_completed(ledger: Ledger, filename: str) -> dict[str, str | int | None]:
    row = ledger.get_by_filename(filename)
    assert row is not None
    ledger.update_status(
        int(row["id"]),
        "completed",
        completed_at="2026-06-04T12:00:00+00:00",
        output_markdown_path=f"output/markdown/{Path(filename).stem}.md",
    )
    refreshed = ledger.get_by_filename(filename)
    assert refreshed is not None
    return refreshed


def test_retry_selects_failed_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_tracked_files(tmp_path, monkeypatch, ["failed.mp3", "done.mp3"])
    install_successful_pipeline_mocks(monkeypatch)
    failed = ledger.get_by_filename("failed.mp3")
    assert failed is not None
    ledger.update_status(int(failed["id"]), "failed_transcription", error_message="bad")
    mark_completed(ledger, "done.mp3")

    result = runner.invoke(app, ["retry"])

    assert result.exit_code == 0
    assert "ScribeFlow Retry Summary" in result.output
    assert ledger.get_by_filename("failed.mp3")["status"] == "completed"
    assert ledger.get_by_filename("done.mp3")["status"] == "completed"


def test_reprocess_can_process_completed_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_tracked_files(tmp_path, monkeypatch, ["complete.mp3"])
    install_successful_pipeline_mocks(monkeypatch)
    mark_completed(ledger, "complete.mp3")

    result = runner.invoke(app, ["reprocess", "--file", "complete.mp3"])

    assert result.exit_code == 0
    row = ledger.get_by_filename("complete.mp3")
    assert row["status"] == "completed"
    assert (tmp_path / str(row["output_audio_path"])).is_file()
    assert (tmp_path / str(row["output_json_path"])).is_file()
    assert (tmp_path / str(row["output_markdown_path"])).is_file()


def test_reprocess_enhance_regenerates_enhanced_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_tracked_files(tmp_path, monkeypatch, ["example.mp3"])
    install_successful_pipeline_mocks(monkeypatch)
    mark_completed(ledger, "example.mp3")

    result = runner.invoke(app, ["reprocess", "--file", "example.mp3", "--enhance"])

    assert result.exit_code == 0
    row = ledger.get_by_filename("example.mp3")
    markdown = (tmp_path / str(row["output_markdown_path"])).read_text(
        encoding="utf-8"
    )
    assert "- Retry works." in markdown
    assert "1. What is Retry?" in markdown


def test_clean_dry_run_does_not_delete_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    audio_path = tmp_path / "working/audio/test.wav"
    write_file(audio_path, b"wav")

    result = runner.invoke(app, ["clean", "--audio", "--dry-run"])

    assert result.exit_code == 0
    assert audio_path.exists()


def test_clean_removes_selected_generated_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    audio_path = tmp_path / "working/audio/test.wav"
    temp_path = tmp_path / "working/temp/test.tmp"
    write_file(audio_path, b"wav")
    write_file(temp_path, b"tmp")

    result = runner.invoke(app, ["clean", "--audio"])

    assert result.exit_code == 0
    assert not audio_path.exists()
    assert temp_path.exists()


def test_archive_moves_completed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_tracked_files(tmp_path, monkeypatch, ["archive_me.mp3"])
    mark_completed(ledger, "archive_me.mp3")

    result = runner.invoke(app, ["archive"])

    assert result.exit_code == 0
    assert not (tmp_path / "inbox/mp3/archive_me.mp3").exists()
    assert (tmp_path / "archive/completed/archive_me.mp3").is_file()


def test_archive_updates_ledger_source_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_tracked_files(tmp_path, monkeypatch, ["update_path.mp3"])
    mark_completed(ledger, "update_path.mp3")

    runner.invoke(app, ["archive"])

    row = ledger.get_by_filename("update_path.mp3")
    assert row["source_path"] == "archive/completed/update_path.mp3"


def test_archive_avoids_filename_collisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_tracked_files(tmp_path, monkeypatch, ["collision.mp3"])
    row = mark_completed(ledger, "collision.mp3")
    write_file(tmp_path / "archive/completed/collision.mp3", b"existing")

    result = runner.invoke(app, ["archive"])

    expected = tmp_path / f"archive/completed/collision_{str(row['file_hash'])[:8]}.mp3"
    assert result.exit_code == 0
    assert expected.is_file()
    assert (tmp_path / "archive/completed/collision.mp3").read_bytes() == b"existing"


def test_archive_dry_run_does_not_move_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_tracked_files(tmp_path, monkeypatch, ["dry_archive.mp3"])
    mark_completed(ledger, "dry_archive.mp3")

    result = runner.invoke(app, ["archive", "--dry-run"])

    assert result.exit_code == 0
    assert (tmp_path / "inbox/mp3/dry_archive.mp3").is_file()
    assert not (tmp_path / "archive/completed/dry_archive.mp3").exists()
    assert ledger.get_by_filename("dry_archive.mp3")["source_path"] == (
        "inbox/mp3/dry_archive.mp3"
    )
