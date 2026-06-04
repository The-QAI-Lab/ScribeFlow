# Testing with Real MP3/MP4 Files

Use short safe files first. Recommended test length is 30 seconds to 2 minutes. Do not start with a one-hour lecture until the small test works.

## Install

```bash
pip install -e .[dev,stt]
ffmpeg -version
```

FFmpeg must be installed separately and available on `PATH`.

## Add Test Files

Place files here:

```text
inbox/mp3/
inbox/mp4/
```

Example:

```text
inbox/mp3/test_lecture.mp3
inbox/mp4/test_video.mp4
```

## Run the MVP Workflow

```bash
scribeflow init
scribeflow scan
scribeflow status
scribeflow process
scribeflow status
```

Optional single-file test:

```bash
scribeflow process --limit 1 --model small --language en
```

Optional enhanced Markdown test:

```bash
scribeflow process --limit 1 --model small --language en --enhance
```

If a job fails after you fix the underlying issue:

```bash
scribeflow retry
```

To regenerate outputs for a tracked file:

```bash
scribeflow reprocess --file "test_lecture.mp3" --model small --language en
```

To regenerate with study-ready sections:

```bash
scribeflow reprocess --file "test_lecture.mp3" --model small --language en --enhance
```

## Expected Outputs

```text
working/audio/*.wav
output/raw_json/*.json
output/markdown/*.md
```

The ledger should show completed jobs after Markdown export succeeds.

Enhancement is deterministic and local-first. It does not call a cloud API and is not the same as LLM summarization. Quality depends on transcript quality and the amount of useful spoken content.

## Cleaning and Archiving

Preview generated working files before deleting them:

```bash
scribeflow clean --all --dry-run
```

Remove generated working audio, temp files, and working logs:

```bash
scribeflow clean --all
```

`clean` does not delete inbox files, archive files, transcript outputs, or the ledger.

After reviewing the Markdown output, preview archive moves:

```bash
scribeflow archive --dry-run
```

Move completed source media into `archive/completed/`:

```bash
scribeflow archive
```

Move failed source media only when you explicitly request it:

```bash
scribeflow archive --failed
```

## Git Safety

Real media files should not be committed. The project ignores local media, generated outputs, local ledgers, and logs:

```gitignore
inbox/mp3/*
inbox/mp4/*
working/audio/*
working/temp/*
working/logs/*
output/raw_json/*
output/markdown/*
output/subtitles/*
archive/completed/*
archive/failed/*
.scribeflow/*
logs/*
*.sqlite
*.sqlite3
*.db
!.gitkeep
```

Because ScribeFlow is often used with class lectures, meetings, and training material, users should only test with files they have the right to process. Do not commit private, copyrighted, FERPA-protected, HIPAA-protected, or confidential recordings to a public repository.

Before committing, verify nothing private is staged:

```bash
git status
```

If media files appear, stop and update `.gitignore` before committing.
