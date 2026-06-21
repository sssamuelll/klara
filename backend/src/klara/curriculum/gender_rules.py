"""Deterministic German gender-suffix rules — a generalization OVER the oracle,
so the per-word oracle gender always wins; a rule surfaces only when it AGREES
with the oracle (or the lemma is a curated closed-exception). Pure, no DB."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

# Hard suffixes: ~100% reliable, teachable AS a rule. (suffix, article)
_HARD: list[tuple[str, str]] = [
    ("chen", "das"),
    ("lein", "das"),
    ("ung", "die"),
    ("heit", "die"),
    ("keit", "die"),
    ("schaft", "die"),
    ("ität", "die"),
    ("tät", "die"),
    ("tion", "die"),
    ("sion", "die"),
    ("ion", "die"),
    ("ling", "der"),
    ("ismus", "der"),
    ("ment", "das"),
    ("tum", "das"),
]
# Tendency suffixes: softened ("usually"), never absolute. Shown only on oracle
# agreement; suppressed (Case B) on disagreement, exactly like a hard suffix.
_TENDENCY: list[tuple[str, str]] = [
    ("e", "die"),
    ("er", "der"),
    ("el", "der"),
    ("en", "der"),
    ("ie", "die"),
    ("ik", "die"),
    ("ur", "die"),
]
# -nis is deliberately ABSENT: it is genuinely two-gendered (die/das), which a
# scalar rule_gender cannot represent, and it is "never a rule" pedagogically.

# Closed, enumerable exceptions to a hard suffix (Case C). Exact-lemma keys only.
_CURATED_EXCEPTIONS: dict[str, str] = {
    "Reichtum": "der",
    "Irrtum": "der",
}

# Stem remaining after stripping the suffix must be at least this many codepoints,
# to avoid firing on absurdly short words.
_MIN_STEM = 2


@dataclass(frozen=True, slots=True)
class GenderRule:
    suffix: str
    rule_gender: str  # der | die | das
    suffix_class: str  # hard | tendency


class GenderRuleDetail(TypedDict):
    suffix: str
    suffix_class: str
    rule_gender: str
    oracle_gender: str
    agreement: bool
    is_exception: bool


def detect_gender_rule(lemma: str) -> GenderRule | None:
    """Longest matching suffix → der/die/das + class. Among equal-length matches,
    hard beats tendency. Returns None when nothing matches with a ≥2-codepoint
    stem. Deliberately simple: false positives (der Schwung vs -ung) are caught
    by reconcile_rule against the oracle, not here."""
    lemma = (lemma or "").strip()
    # candidate key = (suffix_length, hard_priority); pick the max.
    best: tuple[int, int, GenderRule] | None = None
    for table, priority, cls in ((_HARD, 1, "hard"), (_TENDENCY, 0, "tendency")):
        for suffix, article in table:
            if lemma.endswith(suffix) and len(lemma) - len(suffix) >= _MIN_STEM:
                key = (len(suffix), priority)
                if best is None or key > best[:2]:
                    best = (key[0], key[1], GenderRule(suffix, article, cls))
    return best[2] if best is not None else None


def reconcile_rule(rule: GenderRule, oracle_gender: str, lemma: str) -> GenderRuleDetail:
    """Reconcile a detected rule against the authoritative oracle gender. Only
    invoked with a non-None rule (the no-suffix → None guard lives at the call
    site). agreement is the sole show-gate; is_exception is true only when the
    rule disagrees AND the lemma is curated with a value matching the oracle."""
    agreement = rule.rule_gender == oracle_gender
    is_exception = not agreement and _CURATED_EXCEPTIONS.get(lemma) == oracle_gender
    return {
        "suffix": rule.suffix,
        "suffix_class": rule.suffix_class,
        "rule_gender": rule.rule_gender,
        "oracle_gender": oracle_gender,
        "agreement": agreement,
        "is_exception": is_exception,
    }
