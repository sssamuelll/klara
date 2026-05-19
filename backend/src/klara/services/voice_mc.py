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

    picked_index is None if either:
      - the top score is below _MIN_RATIO, OR
      - the gap between top and runner-up is below _MIN_MARGIN
        (ambiguous answer — we don't guess).
    """
    if not transcript.strip() or not options:
        return None, [0.0] * len(options)

    norm_transcript = _normalize(transcript)
    if not norm_transcript:
        return None, [0.0] * len(options)

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
    return scores.index(top), scores
