# ScribeFlow Architecture

ScribeFlow is a local-first Typer CLI backed by a SQLite ledger.

## MVP Flow

```text
MP4/MP3
-> FFmpeg
-> WAV
-> faster-whisper
-> JSON transcript
-> optional deterministic enhancer
-> Markdown transcript
-> ledger completed
```

## Operational Flow

```text
failed_* -> retry -> pending -> process pipeline
completed or tracked file -> reprocess -> regenerated artifacts -> completed
completed source media -> archive/completed -> ledger source_path updated
failed source media + --failed -> archive/failed -> ledger source_path updated
working generated files -> clean -> removed without touching inbox/archive/ledger
```

## Search Flow

```text
output/raw_json/*.json
+ optional output/markdown/*.md sections
-> SQLite FTS5
-> .scribeflow/search.sqlite
-> scribeflow search
```

Search is local-first and deterministic. It indexes completed generated artifacts and does not call cloud APIs. It is not chat/RAG; it returns matching transcript segments and optional Markdown section matches.

## Study Enhancement Flow

```text
transcript JSON segments
-> sentence splitting
-> word-frequency scoring
-> extractive summary
-> study notes
-> key terms
-> study questions
-> enhanced Markdown
```

Enhancement is deterministic and local-first. It does not use cloud APIs or RAG/chat. The enhancer can be skipped entirely; when skipped, Markdown includes placeholder study sections.

## Workspace

```text
inbox/mp3/              input MP3 files
inbox/mp4/              input MP4 files
working/audio/          normalized mono 16 kHz WAV files
working/temp/           reserved temporary workspace
working/logs/           reserved processing logs
output/raw_json/        raw transcript JSON
output/markdown/        timestamped Markdown transcripts
output/subtitles/       reserved subtitle output
.scribeflow/ledger.sqlite
.scribeflow/search.sqlite
```

## Ledger

The ledger stores:
- `id`
- `source_path`
- `original_filename`
- `normalized_filename`
- `file_type`
- `file_size`
- `file_hash`
- `status`
- `discovered_at`
- `started_at`
- `completed_at`
- `output_audio_path`
- `output_markdown_path`
- `output_json_path`
- `output_subtitle_path`
- `error_message`
- `retry_count`

Statuses:
- `pending`
- `audio_extracted`
- `transcribed`
- `markdown_exported`
- `completed`
- `failed_audio`
- `failed_transcription`
- `failed_export`

`completed` is only written after Markdown export succeeds and the Markdown file exists.

## Modules

- `scribeflow.cli` owns Typer commands and Rich output.
- `scribeflow.scanner` scans inbox folders and registers pending rows.
- `scribeflow.ledger` owns SQLite schema, migration, and state updates.
- `scribeflow.media` extracts normalized WAV audio with FFmpeg.
- `scribeflow.transcriber` wraps faster-whisper and raw JSON writing.
- `scribeflow.enhancer` creates deterministic local study sections from transcript segments.
- `scribeflow.exporter` renders timestamped Markdown.
- `scribeflow.indexer` builds and searches a local SQLite FTS5 index.
- `scribeflow.status` reads aggregate ledger state.

## Safety Boundaries

- `clean` only removes files under `working/audio/`, `working/temp/`, and `working/logs/`.
- `clean` does not remove inbox media, archived media, output transcripts, or the ledger.
- `archive` moves source media and updates `source_path`; it does not delete generated transcript outputs.
- Archive filename collisions are resolved with a short file-hash suffix.
- Failed source media is archived only when `scribeflow archive --failed` is used.

## Current Non-Goals

This MVP does not implement a web UI, chat/RAG, cloud/API summarization, or local LLM summarization.
