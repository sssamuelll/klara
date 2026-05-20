"""Tests for the MC voice-pick fuzzy resolver. No Azure dependency —
this is pure Python sequence-matching."""

from __future__ import annotations

from klara.services.voice_mc import resolve_option

_OPTS_ES = [
    "Prefiere ir de pie.",
    "El autobús va lleno.",
    "Hay un perro en su asiento.",
]


def test_exact_match_picks_index():
    picked, scores = resolve_option("El autobús va lleno.", _OPTS_ES)
    assert picked == 1
    assert scores[1] == max(scores)


def test_loose_match_ignores_punctuation_and_case():
    picked, _ = resolve_option("el autobús va lleno", _OPTS_ES)
    assert picked == 1


def test_loose_match_ignores_accents():
    # Azure sometimes returns transcripts without accents.
    picked, _ = resolve_option("el autobus va lleno", _OPTS_ES)
    assert picked == 1


def test_close_paraphrase_still_picks():
    # Missing article — should still land on option 1 if SequenceMatcher
    # gives it a high enough ratio.
    picked, _ = resolve_option("autobús va lleno", _OPTS_ES)
    assert picked == 1


def test_unrelated_input_returns_none():
    picked, _ = resolve_option("buenos días señora", _OPTS_ES)
    assert picked is None


def test_ambiguous_between_two_options_returns_none():
    """When top and runner-up are too close, we refuse to guess."""
    # Two near-identical options, transcript matches both:
    opts = ["el gato come pescado", "el gato come pollo"]
    picked, scores = resolve_option("el gato come", opts)
    # Both options share the first 3 words → top and runner-up tight.
    assert picked is None
    # but both got non-trivial scores
    assert all(s > 0.2 for s in scores)


def test_empty_transcript_returns_none():
    picked, scores = resolve_option("", _OPTS_ES)
    assert picked is None
    assert scores == [0.0, 0.0, 0.0]


def test_whitespace_only_transcript_returns_none():
    picked, _ = resolve_option("   \n  ", _OPTS_ES)
    assert picked is None


def test_empty_options_list_returns_none():
    picked, scores = resolve_option("anything", [])
    assert picked is None
    assert scores == []
