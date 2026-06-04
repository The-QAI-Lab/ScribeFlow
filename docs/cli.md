# ScribeFlow CLI (Phase 1)

This page documents the currently implemented commands:

- `scribeflow version`
- `scribeflow init`
- `scribeflow scan`
- `scribeflow status`
- `scribeflow process`

## `scribeflow version`
Print the installed version.

```bash
scribeflow version
```

Example output:
```text
ScribeFlow 0.1.0
```

## `scribeflow init`
Creates required workspace folders and initializes the local SQLite ledger.

Creates directories if missing:
- `inbox/mp4/`
- `inbox/mp3/`
- `working/audio/`
- `working/temp/`
- `working/logs/`
- `output/markdown/`
- `output/raw_json/`
- `output/subtitles/`
- `archive/completed/`
- `archive/failed/`
- `.scribeflow/`

Creates ledger database:
- `.scribeflow/ledger.sqlite`

Safe to run multiple times.

```bash
scribeflow init
```

Example output:
```text
Workspace ready.
Ledger: .scribeflow/ledger.sqlite
```

## `scribeflow scan`
Scans `inbox/mp3/` and `inbox/mp4/`, processes only `.mp3` and `.mp4`, hashes file contents with SHA-256, and registers new files as `pending`.

Duplicate content hashes are skipped even when filenames differ.

```bash
scribeflow scan
```

Example output:
```text
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

## `scribeflow status`
Shows aggregate ledger counts and a pending-files table.

```bash
scribeflow status
```

Example output:
```text
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

## `scribeflow process`
Processes pending files from the ledger and converts each to mono 16kHz WAV in `working/audio/` using FFmpeg.

Supported:
- `.mp4` → audio extraction (`-vn`) + WAV normalization
- `.mp3` → WAV normalization

Status transitions:
- success → `audio_extracted`
- conversion/missing source failure → `failed_audio`

```bash
scribeflow process
scribeflow process --limit 1
scribeflow process --file lecture.mp4
scribeflow process --dry-run
```
