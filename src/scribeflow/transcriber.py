"""Speech-to-text transcription helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TranscriptionError(RuntimeError):
    """Raised when speech-to-text transcription fails."""


def transcribe_audio(
    audio_path: Path,
    *,
    source_file: str,
    model: str = "small",
    language: str | None = None,
) -> dict[str, Any]:
    """Transcribe audio with faster-whisper and return serializable JSON data."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "faster-whisper is not installed. Install with: pip install -e .[stt]"
        ) from exc

    try:
        whisper_model = WhisperModel(model)
        segments_iter, info = whisper_model.transcribe(
            str(audio_path),
            language=language,
        )
        segments = [
            {
                "id": index,
                "start": float(segment.start),
                "end": float(segment.end),
                "text": str(segment.text).strip(),
            }
            for index, segment in enumerate(segments_iter)
        ]
    except Exception as exc:  # pragma: no cover - exercised through CLI mocks.
        raise TranscriptionError(str(exc)) from exc

    detected_language = language or getattr(info, "language", None)
    duration = getattr(info, "duration", None)
    transcript: dict[str, Any] = {
        "source_file": source_file,
        "audio_file": audio_path.as_posix(),
        "model": model,
        "language": detected_language,
        "segments": segments,
    }
    if duration is not None:
        transcript["duration"] = float(duration)
    return transcript


def write_transcript_json(transcript: dict[str, Any], output_path: Path) -> Path:
    """Write raw transcript JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path
