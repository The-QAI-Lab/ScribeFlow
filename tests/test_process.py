from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from scribeflow.cli import app
from scribeflow.config import LEDGER_PATH
from scribeflow.ledger import Ledger


runner = CliRunner()


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def setup_pending_files(
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
                {"id": 0, "start": 0.0, "end": 4.2, "text": "Welcome."}
            ],
        }

    monkeypatch.setattr("scribeflow.cli.extract_audio", fake_extract_audio)
    monkeypatch.setattr("scribeflow.cli.transcribe_audio", fake_transcribe_audio)


def test_process_command_runs_full_mocked_pipeline_successfully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_pending_files(tmp_path, monkeypatch, ["test_lecture.mp3"])
    install_successful_pipeline_mocks(monkeypatch)

    result = runner.invoke(app, ["process", "--model", "small", "--language", "en"])

    assert result.exit_code == 0
    assert "ScribeFlow Process Summary" in result.output
    assert list((tmp_path / "working/audio").glob("*.wav"))
    assert list((tmp_path / "output/raw_json").glob("*.json"))
    assert list((tmp_path / "output/markdown").glob("*.md"))
    assert ledger.get_by_filename("test_lecture.mp3")["status"] == "completed"


def test_process_marks_completed_after_markdown_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_pending_files(tmp_path, monkeypatch, ["done.mp3"])
    install_successful_pipeline_mocks(monkeypatch)

    runner.invoke(app, ["process"])

    row = ledger.get_by_filename("done.mp3")
    assert row["status"] == "completed"
    assert row["output_markdown_path"]
    assert (tmp_path / str(row["output_markdown_path"])).is_file()


def test_process_marks_failed_audio_when_ffmpeg_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_pending_files(tmp_path, monkeypatch, ["audio_fail.mp3"])

    def fail_audio(input_path: Path, output_path: Path, *, verbose: bool = False):
        raise RuntimeError("ffmpeg bad input")

    monkeypatch.setattr("scribeflow.cli.extract_audio", fail_audio)

    runner.invoke(app, ["process"])

    row = ledger.get_by_filename("audio_fail.mp3")
    assert row["status"] == "failed_audio"
    assert row["retry_count"] == 1
    assert "ffmpeg bad input" in str(row["error_message"])


def test_process_marks_failed_transcription_when_stt_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_pending_files(tmp_path, monkeypatch, ["stt_fail.mp3"])
    install_successful_pipeline_mocks(monkeypatch)

    def fail_stt(
        audio_path: Path,
        *,
        source_file: str,
        model: str = "small",
        language: str | None = None,
    ):
        raise RuntimeError("stt unavailable")

    monkeypatch.setattr("scribeflow.cli.transcribe_audio", fail_stt)

    runner.invoke(app, ["process"])

    row = ledger.get_by_filename("stt_fail.mp3")
    assert row["status"] == "failed_transcription"
    assert row["retry_count"] == 1
    assert "stt unavailable" in str(row["error_message"])


def test_process_marks_failed_export_when_markdown_export_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_pending_files(tmp_path, monkeypatch, ["export_fail.mp3"])
    install_successful_pipeline_mocks(monkeypatch)

    def fail_export(*args, **kwargs):
        raise RuntimeError("markdown failed")

    monkeypatch.setattr("scribeflow.cli.export_markdown", fail_export)

    runner.invoke(app, ["process"])

    row = ledger.get_by_filename("export_fail.mp3")
    assert row["status"] == "failed_export"
    assert row["retry_count"] == 1
    assert "markdown failed" in str(row["error_message"])


def test_dry_run_does_not_change_ledger_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_pending_files(tmp_path, monkeypatch, ["dry.mp3"])
    install_successful_pipeline_mocks(monkeypatch)

    result = runner.invoke(app, ["process", "--dry-run"])

    assert result.exit_code == 0
    assert ledger.get_by_filename("dry.mp3")["status"] == "pending"
    assert not list((tmp_path / "working/audio").glob("*.wav"))


def test_limit_only_processes_requested_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_pending_files(tmp_path, monkeypatch, ["one.mp3", "two.mp3"])
    install_successful_pipeline_mocks(monkeypatch)

    runner.invoke(app, ["process", "--limit", "1"])

    statuses = {
        ledger.get_by_filename("one.mp3")["status"],
        ledger.get_by_filename("two.mp3")["status"],
    }
    assert statuses == {"completed", "pending"}


def test_file_only_processes_selected_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_pending_files(tmp_path, monkeypatch, ["selected.mp3", "other.mp3"])
    install_successful_pipeline_mocks(monkeypatch)

    runner.invoke(app, ["process", "--file", "selected.mp3"])

    assert ledger.get_by_filename("selected.mp3")["status"] == "completed"
    assert ledger.get_by_filename("other.mp3")["status"] == "pending"


def test_process_enhance_writes_enhanced_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = setup_pending_files(tmp_path, monkeypatch, ["enhance.mp3"])
    install_successful_pipeline_mocks(monkeypatch)

    result = runner.invoke(app, ["process", "--enhance"])

    assert result.exit_code == 0
    row = ledger.get_by_filename("enhance.mp3")
    markdown = (tmp_path / str(row["output_markdown_path"])).read_text(
        encoding="utf-8"
    )
    assert "## Summary" in markdown
    assert "- Welcome." in markdown
    assert "## Study Questions" in markdown
    assert "1. " in markdown
