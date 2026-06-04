"""Configuration constants for local workspace layout."""

from pathlib import Path

WORKSPACE_ROOT = Path(".")

REQUIRED_DIRECTORIES = [
    Path("inbox/mp4"),
    Path("inbox/mp3"),
    Path("working/audio"),
    Path("working/temp"),
    Path("working/logs"),
    Path("output/markdown"),
    Path("output/raw_json"),
    Path("output/subtitles"),
    Path("archive/completed"),
    Path("archive/failed"),
    Path(".scribeflow"),
]

INBOX_DIRECTORIES = [
    Path("inbox/mp4"),
    Path("inbox/mp3"),
]

LEDGER_PATH = Path(".scribeflow/ledger.sqlite")
SEARCH_INDEX_PATH = Path(".scribeflow/search.sqlite")

SUPPORTED_EXTENSIONS = {".mp3", ".mp4"}
