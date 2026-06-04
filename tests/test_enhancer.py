from __future__ import annotations

from scribeflow.enhancer import (
    EnhancementOptions,
    enhance_transcript,
    extract_key_terms,
    generate_study_questions,
    generate_summary,
    split_sentences,
)


def test_summary_generation_returns_bullet_points() -> None:
    sentences = split_sentences(
        "Neural networks learn patterns from data. "
        "The loss function measures prediction error. "
        "Backpropagation updates weights to reduce the loss. "
        "Training quality depends on clean examples."
    )

    summary = generate_summary(sentences)

    assert summary
    assert all(isinstance(item, str) and item for item in summary)


def test_key_term_extraction_ignores_stopwords() -> None:
    terms = extract_key_terms(
        split_sentences(
            "The neural network uses a loss function. "
            "The neural network updates model weights."
        )
    )

    normalized = {term.lower() for term in terms}
    assert "the" not in normalized
    assert "neural network" in normalized or "neural" in normalized


def test_study_questions_are_generated_from_transcript_content() -> None:
    sentences = split_sentences(
        "Backpropagation updates model weights. "
        "The loss function measures prediction error."
    )

    questions = generate_study_questions(sentences, ["Backpropagation", "Loss Function"])

    assert questions
    assert any("Backpropagation" in question for question in questions)
    assert all(question.endswith("?") for question in questions)


def test_enhancement_works_without_faster_whisper() -> None:
    transcript = {
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 5.0,
                "text": "Gradient descent updates weights to reduce training loss.",
            }
        ]
    }

    result = enhance_transcript(
        transcript,
        EnhancementOptions(summary=True, notes=True, terms=True, questions=True),
    )

    assert result["summary"]
    assert result["notes"]
    assert result["terms"]
    assert result["questions"]


def test_empty_transcripts_do_not_crash_enhancement() -> None:
    result = enhance_transcript(
        {"segments": []},
        EnhancementOptions(summary=True, notes=True, terms=True, questions=True),
    )

    assert result == {"summary": [], "notes": [], "terms": [], "questions": []}


def test_very_short_transcripts_still_produce_safe_output() -> None:
    result = enhance_transcript(
        {"segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "Hello."}]},
        EnhancementOptions(summary=True, notes=True, terms=True, questions=True),
    )

    assert result["summary"] == ["Hello."]
    assert result["notes"] == ["Hello."]
