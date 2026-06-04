# Local Search

ScribeFlow can build a local SQLite full-text index over generated transcripts.

Search is local-first:
- It reads generated files from `output/raw_json/`.
- It can optionally read study sections from `output/markdown/`.
- It writes the search database to `.scribeflow/search.sqlite`.
- It does not call cloud APIs.
- It does not add chat or RAG behavior.

## Build The Index

After processing files:

```bash
scribeflow index
```

Rebuild from scratch:

```bash
scribeflow index --rebuild
```

Include enhanced Markdown study sections:

```bash
scribeflow index --rebuild --include-markdown
```

By default, indexing updates only new or changed transcript JSON files.

## Search

```bash
scribeflow search "backpropagation"
scribeflow search "neural network" --limit 10
scribeflow search "sensitivity" --source "lecture_name"
scribeflow search "loss function" --json
```

Search results include:
- source file
- timestamp
- matching text snippet
- Markdown path

## Requirements

Search uses SQLite FTS5. Most modern Python SQLite builds include FTS5. If FTS5 is unavailable, ScribeFlow exits with a clear message.

Search does not require FFmpeg or faster-whisper after transcript files already exist.
