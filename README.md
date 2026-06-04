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

## Core Features
- Local-first processing pipeline for MP4 and MP3 lecture files
- Inbox-based workflow (`inbox/mp4/` and `inbox/mp3/`)
- File hashing and deduplication
- SQLite processing ledger for status tracking
- FFmpeg-based extraction and normalization
- `faster-whisper` default speech-to-text backend
- Raw transcript JSON output for downstream tooling
- Optional subtitle output (SRT/VTT)
- Clean timestamped Markdown transcript generation
- Retry and reprocess support for failed or updated files
- Rich terminal UX for status and progress reporting

## Example Workflow
1. Add lecture/video files to `inbox/mp4/`
2. Add audio files to `inbox/mp3/`
3. Run `scribeflow scan`
4. ScribeFlow finds new files and computes content hashes
5. The SQLite ledger is checked for duplicates and prior status
6. New items are marked `pending`
7. Run `scribeflow process` to process all pending items
8. MP4 files are converted to audio via FFmpeg
9. MP3 files are normalized to WAV for stable transcription
10. Speech-to-text runs with `faster-whisper`
11. Raw transcript JSON is written to `output/raw_json/`
12. Optional subtitle files are written to `output/subtitles/`
13. Timestamped Markdown is generated in `output/markdown/`
14. Ledger status updates to `completed`
15. (Optional) Original files are moved to `archive/completed/`
16. Failed jobs are marked `failed` and can be retried with `scribeflow retry`

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
scribeflow init
scribeflow scan
scribeflow process
scribeflow status
```

## CLI Commands
- `scribeflow init` — initialize folders, config, and ledger
- `scribeflow scan` — scan inbox folders and register new files as pending
- `scribeflow status` — show processing counts and recent jobs
- `scribeflow process` — process all pending files end-to-end
- `scribeflow retry` — retry failed jobs
- `scribeflow reprocess --file <filename>` — force reprocess one file
- `scribeflow clean` — clean temporary artifacts and stale intermediate files
- `scribeflow version` — print installed version

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

Recommended location: `.scribeflow/ledger.db`

## File Status Lifecycle
Typical lifecycle for each media file:
1. `discovered`
2. `pending`
3. `processing`
4. `completed` or `failed`
5. `retrying` (when `scribeflow retry` runs)
6. back to `processing`, then terminal state

## Markdown Output Format
Each transcript should be human-readable and machine-parseable:
- title and source metadata
- processing timestamp
- optional model/config metadata
- timestamped sections/segments
- clean paragraph formatting

Example pattern:
- heading with source filename
- section list with `[hh:mm:ss]` markers
- normalized punctuation and paragraph grouping

## Example Markdown Transcript
```markdown
# Lecture Transcript: Intro_to_Bayesian_Stats.mp4

- Source: inbox/mp4/Intro_to_Bayesian_Stats.mp4
- Processed: 2026-06-04T14:23:11Z
- Duration: 00:48:12
- Model: faster-whisper (medium)

## Transcript

[00:00:03] Welcome everyone. Today we are introducing Bayesian thinking and why prior beliefs matter.

[00:02:41] Let us compare frequentist and Bayesian interpretations using a simple coin toss example.

[00:11:09] The posterior combines prior belief and observed evidence in a mathematically explicit way.
```

## Roadmap
Near-term:
- robust `init/scan/process/status/retry/reprocess/clean` command implementation
- stable SQLite schema with migrations
- better failure diagnostics and retry policies

Planned future commands:
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
