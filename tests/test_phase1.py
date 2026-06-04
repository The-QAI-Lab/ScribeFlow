from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scribeflow.cli import app
from scribeflow.config import LEDGER_PATH, REQUIRED_DIRECTORIES
from scribeflow.hashing import sha256_file
from scribeflow.ledger import Ledger
from scribeflow import processor
from scribeflow.status import load_status


runner = CliRunner()


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def ledger_rows(db_path: Path) -> list[dict[str, str]]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT original_filename, status, output_audio_path, error_message
            FROM ledger
            ORDER BY original_filename ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def test_init_creates_required_folders_and_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    for folder in REQUIRED_DIRECTORIES:
        assert (tmp_path / folder).is_dir()
    assert (tmp_path / LEDGER_PATH).is_file()


def test_hashing_is_consistent_sha256(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.mp3"
    payload = b"consistent-bytes-for-hash"
    file_path.write_bytes(payload)

    expected = hashlib.sha256(payload).hexdigest()

    assert sha256_file(file_path) == expected
    assert sha256_file(file_path) == expected


def test_scan_registers_new_mp3_and_mp4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    write_file(tmp_path / "inbox/mp3/lecture-a.mp3", b"mp3-content-a")
    write_file(tmp_path / "inbox/mp4/lecture-b.mp4", b"mp4-content-b")

    result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0
    assert "Files scanned" in result.output
    assert "New files registered" in result.output

    ledger = Ledger(tmp_path / LEDGER_PATH)
    counts = ledger.counts()
    assert counts["total"] == 2
    assert counts["pending"] == 2


def test_scan_skips_duplicates_by_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    duplicate_payload = b"same-content-different-name"
    write_file(tmp_path / "inbox/mp3/first.mp3", duplicate_payload)
    write_file(tmp_path / "inbox/mp4/second.mp4", duplicate_payload)

    first_scan = runner.invoke(app, ["scan"])
    second_scan = runner.invoke(app, ["scan"])

    assert first_scan.exit_code == 0
    assert second_scan.exit_code == 0

    ledger = Ledger(tmp_path / LEDGER_PATH)
    counts = ledger.counts()
    assert counts["total"] == 1
    assert counts["pending"] == 1


def test_status_reads_ledger_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    write_file(tmp_path / "inbox/mp3/pending.mp3", b"pending-bytes")
    runner.invoke(app, ["scan"])

    status = load_status(tmp_path)

    assert status.total == 1
    assert status.pending == 1
    assert status.audio_extracted == 0
    assert status.failed_audio == 0
    assert status.completed == 0
    assert status.failed == 0
    assert len(status.pending_files) == 1
    assert status.pending_files[0]["original_filename"] == "pending.mp3"


def test_process_extracts_audio_for_mp3_and_mp4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    write_file(tmp_path / "inbox/mp3/lecture-a.mp3", b"mp3-a")
    write_file(tmp_path / "inbox/mp4/lecture-b.mp4", b"mp4-b")
    runner.invoke(app, ["scan"])

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        Path(command[-1]).write_bytes(b"wav")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(processor, "_run_ffmpeg", fake_run)

    result = runner.invoke(app, ["process"])

    assert result.exit_code == 0
    assert "Process Summary" in result.output

    rows = ledger_rows(tmp_path / LEDGER_PATH)
    assert len(rows) == 2
    assert all(row["status"] == "audio_extracted" for row in rows)
    assert all(row["output_audio_path"] for row in rows)
    for row in rows:
        assert (tmp_path / str(row["output_audio_path"])).is_file()


def test_process_marks_missing_source_as_failed_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    missing_file = tmp_path / "inbox/mp3/missing.mp3"
    write_file(missing_file, b"missing")
    runner.invoke(app, ["scan"])
    missing_file.unlink()

    result = runner.invoke(app, ["process"])

    assert result.exit_code == 0
    rows = ledger_rows(tmp_path / LEDGER_PATH)
    assert len(rows) == 1
    assert rows[0]["status"] == "failed_audio"
    assert rows[0]["error_message"] is not None
    assert "Source file is missing" in str(rows[0]["error_message"])


def test_process_dry_run_keeps_pending_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    write_file(tmp_path / "inbox/mp3/dry.mp3", b"dry")
    runner.invoke(app, ["scan"])

    result = runner.invoke(app, ["process", "--dry-run"])

    assert result.exit_code == 0
    rows = ledger_rows(tmp_path / LEDGER_PATH)
    assert len(rows) == 1
    assert rows[0]["status"] == "pending"
    assert rows[0]["output_audio_path"] is None


def test_process_supports_limit_and_file_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    write_file(tmp_path / "inbox/mp3/alpha.mp3", b"alpha")
    write_file(tmp_path / "inbox/mp3/beta.mp3", b"beta")
    runner.invoke(app, ["scan"])

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        Path(command[-1]).write_bytes(b"wav")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(processor, "_run_ffmpeg", fake_run)

    first_run = runner.invoke(app, ["process", "--limit", "1"])
    assert first_run.exit_code == 0

    rows = ledger_rows(tmp_path / LEDGER_PATH)
    extracted = [row for row in rows if row["status"] == "audio_extracted"]
    pending = [row for row in rows if row["status"] == "pending"]
    assert len(extracted) == 1
    assert len(pending) == 1

    second_run = runner.invoke(app, ["process", "--file", str(pending[0]["original_filename"])])
    assert second_run.exit_code == 0

    rows = ledger_rows(tmp_path / LEDGER_PATH)
    assert all(row["status"] == "audio_extracted" for row in rows)
