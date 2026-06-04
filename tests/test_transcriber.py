from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from scribeflow.transcriber import transcribe_audio, write_transcript_json


def test_transcript_json_schema_is_correct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeWhisperModel:
        def __init__(self, model: str) -> None:
            self.model = model

        def transcribe(self, audio_path: str, language: str | None = None):
            segment = types.SimpleNamespace(start=0.0, end=4.2, text=" Welcome. ")
            info = types.SimpleNamespace(language=language, duration=4.2)
            return [segment], info

    fake_module = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    audio_path = tmp_path / "lecture.wav"
    audio_path.write_bytes(b"wav")

    transcript = transcribe_audio(
        audio_path,
        source_file="inbox/mp3/test_lecture.mp3",
        model="small",
        language="en",
    )
    output_path = tmp_path / "raw.json"
    write_transcript_json(transcript, output_path)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved["source_file"] == "inbox/mp3/test_lecture.mp3"
    assert saved["audio_file"] == audio_path.as_posix()
    assert saved["model"] == "small"
    assert saved["language"] == "en"
    assert saved["duration"] == 4.2
    assert saved["segments"] == [
        {"id": 0, "start": 0.0, "end": 4.2, "text": "Welcome."}
    ]
