"""Deterministic local transcript enhancement."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


STOPWORDS = {
    "a",
    "about",
    "after",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "like",
    "may",
    "me",
    "might",
    "more",
    "most",
    "no",
    "not",
    "of",
    "on",
    "or",
    "our",
    "so",
    "some",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "you",
    "your",
}

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")
SENTENCE_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)")


@dataclass(frozen=True, slots=True)
class EnhancementOptions:
    summary: bool = False
    notes: bool = False
    terms: bool = False
    questions: bool = False

    @classmethod
    def from_flags(
        cls,
        *,
        enhance: bool,
        summary: bool,
        notes: bool,
        terms: bool,
        questions: bool,
    ) -> "EnhancementOptions":
        if enhance:
            return cls(summary=True, notes=True, terms=True, questions=True)
        return cls(summary=summary, notes=notes, terms=terms, questions=questions)

    def any_enabled(self) -> bool:
        return self.summary or self.notes or self.terms or self.questions


def enhance_transcript(
    transcript: dict[str, Any],
    options: EnhancementOptions,
) -> dict[str, list[str]]:
    """Build deterministic local study sections from transcript segments."""
    sentences = transcript_sentences(transcript)
    terms = extract_key_terms(sentences) if options.terms or options.questions else []
    enhancements: dict[str, list[str]] = {}
    if options.summary:
        enhancements["summary"] = generate_summary(sentences)
    if options.notes:
        enhancements["notes"] = generate_study_notes(sentences)
    if options.terms:
        enhancements["terms"] = terms
    if options.questions:
        enhancements["questions"] = generate_study_questions(sentences, terms)
    return enhancements


def transcript_sentences(transcript: dict[str, Any]) -> list[str]:
    """Extract readable sentences from transcript segments."""
    text = " ".join(
        str(segment.get("text", "")).strip()
        for segment in transcript.get("segments", [])
        if str(segment.get("text", "")).strip()
    )
    return split_sentences(text)


def split_sentences(text: str) -> list[str]:
    """Split transcript text into simple sentence units."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    sentences = [match.group(0).strip() for match in SENTENCE_RE.finditer(normalized)]
    return [sentence for sentence in sentences if sentence]


def generate_summary(sentences: list[str], *, limit: int = 8) -> list[str]:
    """Return up to 5-8 extractive summary bullets."""
    selected = _rank_sentences(sentences, limit=limit, min_words=4)
    if not selected and sentences:
        selected = sentences[: min(3, len(sentences))]
    return selected


def generate_study_notes(sentences: list[str], *, limit: int = 10) -> list[str]:
    """Return readable study-note bullets from important transcript sentences."""
    selected = _rank_sentences(sentences, limit=limit, min_words=3)
    if not selected and sentences:
        selected = sentences[: min(5, len(sentences))]
    return [sentence.rstrip(".!?") + "." for sentence in selected]


def extract_key_terms(sentences: list[str], *, limit: int = 25) -> list[str]:
    """Extract frequent meaningful terms and short phrases."""
    tokens = _meaningful_tokens(" ".join(sentences))
    if not tokens:
        return []

    unigram_counts = Counter(tokens)
    phrase_counts: Counter[str] = Counter()
    for size in (3, 2):
        for index in range(0, max(0, len(tokens) - size + 1)):
            phrase = " ".join(tokens[index : index + size])
            if len(set(phrase.split())) > 1:
                phrase_counts[phrase] += 1

    scored: list[tuple[float, str]] = []
    for phrase, count in phrase_counts.items():
        if count > 1 or len(phrase.split()) == 3:
            scored.append((count * (1 + len(phrase.split()) * 0.5), phrase))
    for token, count in unigram_counts.items():
        scored.append((float(count), token))

    terms: list[str] = []
    seen: set[str] = set()
    for _, term in sorted(scored, key=lambda item: (-item[0], item[1])):
        if term in seen:
            continue
        if any(term in existing or existing in term for existing in seen):
            continue
        seen.add(term)
        terms.append(_title_term(term))
        if len(terms) >= limit:
            break
    return terms


def generate_study_questions(
    sentences: list[str],
    terms: list[str],
    *,
    limit: int = 8,
) -> list[str]:
    """Generate simple deterministic review questions."""
    questions: list[str] = []
    for term in terms[:4]:
        questions.append(f"What is {term}?")

    for sentence in _rank_sentences(sentences, limit=limit, min_words=5):
        words = _meaningful_tokens(sentence)
        if not words:
            continue
        subject = _title_term(" ".join(words[: min(3, len(words))]))
        if "why" not in {question[:3].lower() for question in questions}:
            questions.append(f"Why is {subject} important?")
        else:
            questions.append(f"How does {subject} relate to the lecture topic?")
        if len(questions) >= limit:
            break

    if not questions and sentences:
        questions.append("What is the main idea of this transcript?")
    return _dedupe(questions)[:limit]


def _rank_sentences(
    sentences: list[str],
    *,
    limit: int,
    min_words: int,
) -> list[str]:
    if not sentences:
        return []
    frequencies = Counter(_meaningful_tokens(" ".join(sentences)))
    if not frequencies:
        return sentences[: min(limit, len(sentences))]

    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        words = _meaningful_tokens(sentence)
        if len(words) < min_words:
            continue
        score = sum(frequencies[word] for word in words) / max(len(words), 1)
        scored.append((score, index, sentence.strip()))

    selected = sorted(scored, key=lambda item: (-item[0], item[1]))[:limit]
    return [sentence for _, _, sentence in sorted(selected, key=lambda item: item[1])]


def _meaningful_tokens(text: str) -> list[str]:
    return [
        token.lower().strip("'")
        for token in WORD_RE.findall(text)
        if len(token) > 2 and token.lower().strip("'") not in STOPWORDS
    ]


def _title_term(term: str) -> str:
    return " ".join(word.capitalize() for word in term.split())


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
