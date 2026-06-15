"""Pure analysis of an unscripted pronunciation assessment for Speak.

Takes Azure's ScoreResponse (IPA phoneme alphabet) and a focus-phoneme set,
returns per-word tokens with clarity bands, the focus target word, and the
turn-level focus flags. No I/O — unit-testable without Azure.

Focus sets are FAMILIES of allophones, not single symbols: German ü surfaces
as short /ʏ/ (fünf) and long /yː/ (Tür). Matching normalizes length marks and
combining diacritics away, but display strings (expected_ipa) keep them.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from klara.pronunciation.schemas import ScoreResponse, WordScore

# Per-language focus families for v1 (German-only). The frontend mirrors this
# table for display (lib/speakFocus.ts); the router validates client-sent
# phoneme lists against it so an unexpected symbol fails loudly, not as a
# silent never-matching no-op.
FOCUS_PHONEME_SETS: dict[str, list[str]] = {
    "de": ["y", "ʏ"],
}

# Same cuts as the frontend's scoreBand (lib/pronunciation.ts, issue #40) and
# the practice queue's struggled threshold.
GOOD_THRESHOLD = 70.0
OK_THRESHOLD = 45.0

# Length / suprasegmental marks that vary between allophone notations.
_LENGTH_MARKS = {"ː", "ˑ"}


def normalize_phoneme(phoneme: str) -> str:
    """Normalize an IPA phoneme for matching: strip length marks and
    combining diacritics (ɐ̯ → ɐ, yː → y). Base letters are preserved —
    /ʏ/ and /y/ stay distinct; focus sets list both when they are a family."""
    decomposed = unicodedata.normalize("NFD", phoneme)
    kept = [ch for ch in decomposed if not unicodedata.combining(ch) and ch not in _LENGTH_MARKS]
    return unicodedata.normalize("NFC", "".join(kept))


def scoreband(accuracy: float) -> str:
    if accuracy >= GOOD_THRESHOLD:
        return "good"
    if accuracy >= OK_THRESHOLD:
        return "ok"
    return "bad"


def word_focus_accuracy(word: WordScore, focus_phonemes: list[str]) -> float | None:
    """Lowest accuracy among the word's focus phonemes, or None if the word
    contains no focus phoneme."""
    focus = {normalize_phoneme(p) for p in focus_phonemes}
    matched = [p.accuracy_score for p in word.phonemes if normalize_phoneme(p.phoneme) in focus]
    return min(matched) if matched else None


def expected_ipa(word: WordScore) -> str:
    """Display IPA for the word as Azure expects it — keeps length marks."""
    return "/" + "".join(p.phoneme for p in word.phonemes) + "/"


@dataclass
class TokenAnalysis:
    t: str
    s: str  # "good" | "ok" | "bad"
    focus: bool


@dataclass
class TargetAnalysis:
    word: str
    focus_accuracy: float
    should_ipa: str


@dataclass
class TurnAnalysis:
    tokens: list[TokenAnalysis] = field(default_factory=list)
    target: TargetAnalysis | None = None
    focus_hit: bool = False
    focus_clear: bool = False


def analyze_turn(score: ScoreResponse, focus_phonemes: list[str]) -> TurnAnalysis:
    tokens: list[TokenAnalysis] = []
    focus_accuracies: list[tuple[WordScore, float]] = []

    for word in score.words:
        acc = word_focus_accuracy(word, focus_phonemes)
        tokens.append(
            TokenAnalysis(t=word.word, s=scoreband(word.accuracy_score), focus=acc is not None)
        )
        if acc is not None:
            focus_accuracies.append((word, acc))

    if not focus_accuracies:
        return TurnAnalysis(tokens=tokens, target=None, focus_hit=False, focus_clear=False)

    worst_word, worst_acc = min(focus_accuracies, key=lambda pair: pair[1])
    target = TargetAnalysis(
        word=worst_word.word,
        focus_accuracy=worst_acc,
        should_ipa=expected_ipa(worst_word),
    )
    return TurnAnalysis(
        tokens=tokens,
        target=target,
        focus_hit=True,
        # Clear only when EVERY focus phoneme this turn met the bar — one
        # muddy ü in an otherwise fine sentence is not "clear".
        focus_clear=all(acc >= GOOD_THRESHOLD for _, acc in focus_accuracies),
    )
