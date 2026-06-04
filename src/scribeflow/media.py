"""Media extraction helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scribeflow.utils import normalize_filename


class AudioExtractionError(RuntimeError):
    """Raised when FFmpeg cannot normalize an input media file."""


def normalized_audio_path(root: Path, original_filename: str, file_hash: str) -> Path:
    """Build the deterministic normalized WAV path for a tracked file."""
    safe_name = Path(normalize_filename(original_filename)).stem
    return root / "working/audio" / f"{safe_name}_{file_hash[:8]}.wav"


def extract_audio(input_path: Path, output_path: Path, *, verbose: bool = False) -> Path:
    """Extract mono 16 kHz WAV audio from an MP3 or MP4 file with FFmpeg."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
    ]
    if input_path.suffix.lower() == ".mp4":
        command.append("-vn")
    command.extend(["-ac", "1", "-ar", "16000", str(output_path)])

    result = subprocess.run(
        command,
        check=False,
        capture_output=not verbose,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip() if not verbose else ""
        summary = stderr.splitlines()[-1] if stderr else "FFmpeg failed"
        raise AudioExtractionError(summary)

    return output_path
