from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scribeflow.cli import app
from scribeflow.config import LEDGER_PATH, REQUIRED_DIRECTORIES
from scribeflow.hashing import sha256_file
from scribeflow.ledger import Ledger
from scribeflow.status import load_status


runner = CliRunner()


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


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
    assert status.completed == 0
    assert status.failed == 0
    assert len(status.pending_files) == 1
    assert status.pending_files[0]["original_filename"] == "pending.mp3"
