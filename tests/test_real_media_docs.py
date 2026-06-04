from __future__ import annotations

from pathlib import Path


def test_real_media_docs_include_safety_and_git_checks() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    docs = Path("docs/testing-real-media.md").read_text(encoding="utf-8")
    combined = readme + "\n" + docs

    assert "## Testing With Real MP3/MP4 Files" in readme
    assert "30 seconds to 2 minutes" in combined
    assert "inbox/mp3/test_lecture.mp3" in combined
    assert "output/raw_json/*.json" in combined
    assert "FERPA-protected" in combined
    assert "HIPAA-protected" in combined
    assert "git status" in combined
