"""Voice-pick resolution for Finish quiz MC questions.

The user reads one of the options aloud; we transcribe via Azure STT and
fuzzy-match against the option strings. Returns the picked index (or None
if no option is a strong enough match — the UI then prompts a retry).

Why fuzzy match instead of exact? Real audio gets stripped of punctuation,
sometimes drops articles, occasionally substitutes synonyms ("el bus" vs
"el autobús"). A SequenceMatcher.ratio threshold strikes a balance between
"basically said it right" and "said something else entirely".
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_MIN_RATIO = 0.40
_MIN_MARGIN = 0.10  # winner must beat runner-up by at least this much
# Char-level SequenceMatcher is noisy on unrelated phrases — "buenos días
# señora" shares enough characters with "hay un perro en su asiento" to
# spuriously clear 0.40. Require also that at least one *content* word
# overlaps, which is closer to "the user actually said part of this option".
_MIN_WORD_OVERLAP = 1

# Function words that don't carry semantic weight; they don't count toward
# the overlap requirement. Multi-language because options arrive in the
# story's target_language.
_STOPWORDS = {
    # Spanish
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "y",
    "o",
    "de",
    "del",
    "en",
    "a",
    "al",
    "no",
    "si",
    "es",
    "se",
    # English
    "the",
    "an",
    "and",
    "or",
    "of",
    "in",
    "to",
    "is",
    "it",
    "on",
    # German
    "der",
    "die",
    "das",
    "ein",
    "eine",
    "und",
    "oder",
    "ist",
    "im",
    # French
    "le",
    "les",
    "des",
    "et",
    "ou",
    "à",
    "au",
    "aux",
    # Portuguese
    "os",
    "as",
    "um",
    "uma",
    "uns",
    "umas",
    "e",
    "do",
    "da",
    "na",
}


def _content_words(s: str) -> set[str]:
    """Return set of normalized content words (length >= 2, not stopwords)."""
    return {w for w in s.split() if len(w) >= 2 and w not in _STOPWORDS}


def _normalize(s: str) -> str:
    """Lowercase, strip punctuation, strip accents, collapse whitespace.

    "El autobús va lleno." → "el autobus va lleno"
    """
    s = s.strip().lower()
    # Strip accents/diacritics — Azure sometimes returns them, sometimes not.
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Drop punctuation
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def resolve_option(transcript: str, options: list[str]) -> tuple[int | None, list[float]]:
    """Return (picked_index, per_option_scores).

    picked_index is None if any of these holds:
      - top score is below _MIN_RATIO,
      - top score doesn't beat runner-up by _MIN_MARGIN (ambiguous), or
      - top option shares fewer than _MIN_WORD_OVERLAP content words with
        the transcript (char-level false positive guard).
    """
    if not transcript.strip() or not options:
        return None, [0.0] * len(options)

    norm_transcript = _normalize(transcript)
    if not norm_transcript:
        return None, [0.0] * len(options)

    transcript_words = _content_words(norm_transcript)

    scores: list[float] = []
    for opt in options:
        norm_opt = _normalize(opt)
        if not norm_opt:
            scores.append(0.0)
            continue
        ratio = SequenceMatcher(None, norm_transcript, norm_opt).ratio()
        scores.append(ratio)

    sorted_scores = sorted(scores, reverse=True)
    top = sorted_scores[0]
    runner_up = sorted_scores[1] if len(sorted_scores) > 1 else 0.0

    if top < _MIN_RATIO:
        return None, scores
    if top - runner_up < _MIN_MARGIN:
        return None, scores
    top_idx = scores.index(top)
    overlap = len(transcript_words & _content_words(_normalize(options[top_idx])))
    if overlap < _MIN_WORD_OVERLAP:
        return None, scores
    return top_idx, scores
