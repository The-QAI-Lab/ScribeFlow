# ScribeFlow CLI

## Commands

### `scribeflow version`
Print the installed version.

```bash
scribeflow version
```

### `scribeflow init`
Create required workspace folders and initialize `.scribeflow/ledger.sqlite`.

```bash
scribeflow init
```

Safe to run multiple times.

### `scribeflow scan`
Scan `inbox/mp3/` and `inbox/mp4/`, hash `.mp3` and `.mp4` files, and register new files as `pending`.

```bash
scribeflow scan
```

Duplicate content hashes are skipped even when filenames differ.

### `scribeflow status`
Show aggregate ledger counts and pending files.

```bash
scribeflow status
```

### `scribeflow process`
Process pending files through the MVP pipeline:

```text
pending file -> FFmpeg WAV -> faster-whisper JSON -> Markdown -> completed
```

```bash
scribeflow process
```

Options:
- `--limit N` processes only N pending files.
- `--file "test_lecture.mp3"` processes one tracked file by original filename or source path.
- `--dry-run` shows selected files without writing outputs or changing ledger status.
- `--model small` overrides the faster-whisper model. Default is `small`.
- `--language en` passes a language hint to faster-whisper.
- `--verbose` allows detailed FFmpeg output.
- `--enhance` enables all deterministic study-ready Markdown sections.
- `--summary` generates only summary bullets.
- `--terms` extracts only key terms.
- `--questions` generates only study questions.
- `--notes` generates only study notes.

Examples:
```bash
scribeflow process --limit 1
scribeflow process --file "test_lecture.mp3"
scribeflow process --dry-run
scribeflow process --model medium --language en
scribeflow process --enhance
scribeflow process --summary --terms
```

Summary output:
```text
ScribeFlow Process Summary

Files selected: 2
Audio extracted: 2
Transcribed: 2
Markdown exported: 2
Completed: 2
Failed: 0
```

### `scribeflow retry`
Select jobs with `failed_audio`, `failed_transcription`, or `failed_export`, reset them to `pending`, and run the normal processing pipeline.

```bash
scribeflow retry
scribeflow retry --limit 1
scribeflow retry --model small --language en
```

Failures during retry increment `retry_count` through the same failure handling used by `process`.

### `scribeflow reprocess`
Regenerate WAV, raw JSON, and Markdown for one tracked file, including a file that is already `completed`.

```bash
scribeflow reprocess --file "test_lecture.mp3"
scribeflow reprocess --file "inbox/mp3/test_lecture.mp3" --model medium --language en
scribeflow reprocess --file "test_lecture.mp3" --force
```

Options:
- `--file` selects by original filename or ledger source path.
- `--model` overrides the faster-whisper model.
- `--language` passes a language hint.
- `--force` explicitly allows overwriting generated outputs.
- `--enhance` enables all deterministic study-ready Markdown sections.
- `--summary`, `--terms`, `--questions`, and `--notes` enable individual sections.

Examples with enhancement:
```bash
scribeflow reprocess --file "test_lecture.mp3" --enhance
scribeflow reprocess --file "test_lecture.mp3" --summary --questions
```

## Markdown Enhancement
Study-ready Markdown enhancement is deterministic and local-first. It does not call OpenAI, Gemini, Claude, or any other cloud API.

Available enhancement sections:
- summary
- study notes
- key terms
- study questions

`--enhance` enables all sections. Individual flags enable only the requested sections. If no enhancement flag is passed, ScribeFlow keeps placeholder sections in the Markdown file.

Enhancement is not the same as LLM summarization. It uses local transcript text, word-frequency scoring, and simple question templates. Quality depends on transcript quality and the amount of useful source text.

### `scribeflow clean`
Remove generated working files without deleting source media or the ledger.

```bash
scribeflow clean --audio
scribeflow clean --temp
scribeflow clean --logs
scribeflow clean --all
scribeflow clean --all --dry-run
```

Targets:
- `--audio` removes files under `working/audio/`.
- `--temp` removes files under `working/temp/`.
- `--logs` removes files under `working/logs/`.
- `--all` selects all clean targets.
- `--dry-run` prints selected files without deleting them.

`clean` never removes inbox media, archive media, or `.scribeflow/ledger.sqlite`.

### `scribeflow archive`
Move source media after processing.

```bash
scribeflow archive --dry-run
scribeflow archive
scribeflow archive --failed
```

Behavior:
- Completed source files move to `archive/completed/`.
- Failed source files move to `archive/failed/` only with `--failed`.
- `source_path` is updated in the ledger after each move.
- Existing destination names are protected by adding a short hash suffix.
- `--dry-run` prints planned moves without moving files or updating the ledger.

### `scribeflow index`
Build or update the local SQLite FTS search index from generated transcript JSON files.

```bash
scribeflow index
scribeflow index --rebuild
scribeflow index --include-markdown
scribeflow index --rebuild --include-markdown
```

Options:
- `--rebuild` deletes and recreates `.scribeflow/search.sqlite`.
- `--include-markdown` also indexes Summary, Study Notes, Key Terms, and Study Questions from `output/markdown/`.

By default, `index` only updates new or changed transcript JSON files.

### `scribeflow search`
Search the local index.

```bash
scribeflow search "backpropagation"
scribeflow search "neural network" --limit 10
scribeflow search "sensitivity" --source "lecture_name"
scribeflow search "loss function" --json
```

Options:
- `--limit N` limits returned matches.
- `--source "text"` filters by source filename/path substring.
- `--json` prints machine-readable JSON.

Search returns source file, timestamp, matching snippet, and Markdown path. It does not require FFmpeg or faster-whisper once transcripts already exist.

## Outputs
Generated files are written to:

```text
working/audio/*.wav
output/raw_json/*.json
output/markdown/*.md
.scribeflow/search.sqlite
```

## Dependencies
Base development install:
```bash
pip install -e .[dev]
```

Install speech-to-text support:
```bash
pip install -e .[dev,stt]
```

FFmpeg must be installed separately and available on `PATH`.
