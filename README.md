# ScribeFlow

> Local-first CLI for converting MP4/MP3 lectures into timestamped Markdown transcripts.

## Project Overview
ScribeFlow is an open-source, local-first transcription workflow for people who want structured notes from recorded audio or video.

It is designed for students, researchers, educators, and builders who need:
- reproducible transcript generation,
- clear file tracking,
- clean Markdown outputs suitable for study, search, and AI/RAG workflows,
- a privacy-friendly workflow that can run fully on local machines.

## Why ScribeFlow Exists
Most transcription workflows are fragmented: one tool for conversion, another for transcription, another for cleanup, and no reliable ledger to track what was processed.

ScribeFlow solves this by combining ingestion, normalization, transcription, and Markdown formatting in one CLI workflow with a local SQLite ledger to prevent duplicate work.

## Core Features (Phase 1)
- Local-first ingestion pipeline for MP4 and MP3 files
- Inbox-based workflow (`inbox/mp4/` and `inbox/mp3/`)
- SHA-256 file hashing with chunked reads for large files
- Duplicate prevention by content hash (not filename)
- SQLite ledger for file tracking and status counts
- Idempotent workspace initialization (`scribeflow init`)
- Rich terminal summaries for scan and status commands

## Example Workflow (Current)
1. Run `scribeflow init` to create workspace folders and ledger
2. Add media files to `inbox/mp4/` and/or `inbox/mp3/`
3. Run `scribeflow scan`
4. ScribeFlow scans inbox files, hashes content, and skips duplicate hashes
5. New files are registered in SQLite with status `pending`
6. Run `scribeflow status` to see totals and pending queue

## Folder Structure
```text
ScribeFlow/
├── archive/
│   ├── completed/
│   └── failed/
├── config/
│   └── scribeflow.example.toml
├── docs/
│   ├── ARCHITECTURE.md
│   └── CONFIGURATION.md
├── inbox/
│   ├── mp3/
│   └── mp4/
├── logs/
├── output/
│   ├── markdown/
│   ├── raw_json/
│   └── subtitles/
├── scripts/
│   └── bootstrap.sh
├── src/
│   └── scribeflow/
│       ├── __main__.py
│       ├── cli.py
│       ├── commands/
│       ├── core/
│       └── pipeline/
├── tests/
├── .scribeflow/
│   └── (sqlite ledger lives here)
├── pyproject.toml
├── LICENSE
└── README.md
```

## Installation Requirements
- Python 3.11+
- FFmpeg available on PATH
- OS: macOS, Linux, or Windows (WSL recommended on Windows)

## FFmpeg Requirement
ScribeFlow depends on FFmpeg for media extraction and normalization.

Check installation:
```bash
ffmpeg -version
```

Install examples:
- macOS (Homebrew): `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- Windows (choco): `choco install ffmpeg`

## Python Setup
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
```

## Basic Usage
```bash
scribeflow version
scribeflow init
scribeflow scan
scribeflow status
```

## CLI Commands
- `scribeflow version` — print installed version
- `scribeflow init` — initialize folders and local SQLite ledger
- `scribeflow scan` — scan inbox folders and register new files as pending
- `scribeflow status` — show tracked totals and pending files table

Planned later:
- `scribeflow process`
- `scribeflow retry`
- `scribeflow reprocess --file <filename>`
- `scribeflow clean`

## Configuration
Configuration is expected to be file-based (TOML/YAML support planned; TOML shown by default).

Suggested config surface:
- input/output directories
- archive behavior
- transcription model + device settings
- subtitle output toggle (SRT/VTT)
- hashing and duplicate strategy
- retries and failure policy
- logging verbosity

See `/config/scribeflow.example.toml` and `/docs/CONFIGURATION.md`.

## How the SQLite Ledger Works
ScribeFlow keeps a local SQLite database to persist processing state.

Recommended ledger responsibilities:
- track canonical file path and content hash
- track status transitions (`discovered` -> `pending` -> `processing` -> `completed`/`failed`)
- store attempt count and timestamps
- record output artifact locations
- avoid duplicate processing by hash match

Current location: `.scribeflow/ledger.sqlite`

## File Status Lifecycle
Current statuses implemented in Phase 1:
1. `pending`
2. `completed`
3. `failed`

Phase 1 behavior registers new files as `pending` and reports counts by status.

## Markdown Output Format
Markdown transcript rendering is planned for a later phase.
The output folders already exist (`output/markdown`, `output/raw_json`, `output/subtitles`) but are not written in Phase 1.

## Example Command Output
```text
$ scribeflow scan
            Scan Summary            
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric                     ┃ Count ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Files scanned              │     3 │
│ New files registered       │     2 │
│ Duplicates skipped         │     1 │
│ Unsupported files ignored  │     0 │
└────────────────────────────┴───────┘
```

```text
$ scribeflow status
         Ledger Status         
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric                ┃ Count ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total files tracked   │     2 │
│ Pending               │     2 │
│ Completed             │     0 │
│ Failed                │     0 │
└───────────────────────┴───────┘
```

## Roadmap
Near-term:
- robust `init/scan/process/status/retry/reprocess/clean` command implementation
- stable SQLite schema with migrations
- better failure diagnostics and retry policies

Planned future commands:
- `scribeflow process`
- `scribeflow retry`
- `scribeflow reprocess --file <filename>`
- `scribeflow clean`
- `scribeflow watch`
- `scribeflow summarize`
- `scribeflow quiz`
- `scribeflow terms`
- `scribeflow index`
- `scribeflow search`

Long-term:
- additional STT backends (`whisper.cpp`, hosted APIs)
- semantic indexing and retrieval support
- plugin architecture for custom post-processing

## Development Setup
```bash
git clone https://github.com/The-QAI-Lab/ScribeFlow.git
cd ScribeFlow
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Testing
```bash
pytest -q
```

## Contributing
Contributions are welcome.

Suggested flow:
1. Fork and create a feature branch
2. Add tests for behavior changes
3. Run `pytest`
4. Open a PR with clear context and examples

Please keep changes focused, documented, and reproducible.

## License Placeholder
ScribeFlow is currently released under the MIT License (see `/LICENSE`).

If licensing strategy changes before 1.0, this section will be updated with migration guidance.

## Disclaimer
Transcription quality depends on audio quality, speaker clarity, domain vocabulary, and model selection.

ScribeFlow may produce errors and should be reviewed before use in academic, legal, medical, or business-critical contexts.
