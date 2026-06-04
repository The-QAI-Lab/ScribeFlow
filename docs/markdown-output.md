# Markdown Output

ScribeFlow writes Markdown transcripts to:

```text
output/markdown/
```

## Default Format

When no enhancement flags are passed, Markdown includes metadata, placeholder study sections, and the timestamped transcript:

```markdown
# Lecture Title

**Source file:** test_lecture.mp3
**Media type:** MP3
**Processed:** YYYY-MM-DD HH:MM
**Model:** faster-whisper-small
**Status:** Completed

---

## Summary

Summary generation is not implemented yet.

---

## Study Notes

Study note generation is not implemented yet.

---

## Key Terms

Key term extraction is not implemented yet.

---

## Study Questions

Study question generation is not implemented yet.

---

## Timestamped Transcript
```

## Enhanced Format

Use `--enhance` to generate all study-ready sections:

```bash
scribeflow process --enhance
scribeflow reprocess --file "test_lecture.mp3" --enhance
```

Use individual flags to generate only selected sections:

```bash
scribeflow process --summary
scribeflow process --terms
scribeflow process --questions
scribeflow process --notes
```

Enhanced Markdown keeps the timestamped transcript and fills the study sections:

```markdown
## Summary

- Bullet point summary.

---

## Study Notes

- Important concept from the lecture.

---

## Key Terms

- Term 1
- Term 2

---

## Study Questions

1. Question?
2. Question?

---

## Timestamped Transcript
```

## Local-First Behavior

Enhancement is deterministic and local-first. It works from transcript JSON segments using sentence splitting, word-frequency scoring, key-term extraction, and simple question templates.

It does not call OpenAI, Gemini, Claude, or any cloud API. It is not the same as LLM summarization. Quality depends on transcript quality, source audio, speaker clarity, and whether the transcript contains enough useful content.

Future versions may support local LLMs or optional API-based summarization.

## Search

Markdown files can be included in the local search index:

```bash
scribeflow index --include-markdown
```

When Markdown indexing is enabled, ScribeFlow indexes these sections:
- Summary
- Study Notes
- Key Terms
- Study Questions

The timestamped transcript is indexed from `output/raw_json/*.json`, not by parsing Markdown. This keeps timestamps tied to structured transcript segment data.
