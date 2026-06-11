"""Unit tests for the Speak turn analysis — pure functions, no Azure, no DB.

The correctness core of Speak: focus-phoneme matching must catch BOTH German ü
allophones — short /ʏ/ (fünf) and long /yː/ (Tür) — per the runtime review
(Halberg B5): shipping `ü` as a single "yː" string misses the feature's own
demo word.
"""

from __future__ import annotations

from klara.pronunciation.schemas import (
    PhonemeScore,
    PronunciationScores,
    ScoreResponse,
    WordScore,
)
from klara.services.speak_analysis import (
    FOCUS_PHONEME_SETS,
    analyze_turn,
    expected_ipa,
    normalize_phoneme,
    scoreband,
    word_focus_accuracy,
)


def _word(text: str, accuracy: float, phonemes: list[tuple[str, float]]) -> WordScore:
    return WordScore(
        word=text,
        accuracy_score=accuracy,
        error_type="None",
        phonemes=[PhonemeScore(phoneme=p, accuracy_score=a) for p, a in phonemes],
    )


def _response(words: list[WordScore], text: str | None = None) -> ScoreResponse:
    return ScoreResponse(
        recognized_text=text if text is not None else " ".join(w.word for w in words),
        reference_text="",
        language="de-DE",
        scores=PronunciationScores(
            accuracy=80.0, fluency=75.0, completeness=100.0, pronunciation=78.0
        ),
        words=words,
    )


FUENF = _word("fünf", 55.0, [("f", 90.0), ("ʏ", 40.0), ("n", 88.0), ("f", 91.0)])
TUER = _word("Tür", 82.0, [("t", 95.0), ("yː", 75.0), ("ɐ̯", 80.0)])
MINUTEN = _word("Minuten", 92.0, [("m", 95.0), ("i", 96.0), ("n", 90.0)])

UE_FOCUS = ["y", "ʏ"]


# ---- normalize_phoneme -------------------------------------------------


def test_normalize_strips_length_mark():
    assert normalize_phoneme("yː") == "y"


def test_normalize_keeps_short_allophone_distinct():
    assert normalize_phoneme("ʏ") == "ʏ"


def test_normalize_strips_combining_diacritics():
    # ɐ̯ is ɐ + U+032F (non-syllabic) — diacritics must not break matching
    assert normalize_phoneme("ɐ̯") == "ɐ"


def test_normalize_plain_passthrough():
    assert normalize_phoneme("f") == "f"


# ---- focus matching: BOTH ü allophones ----------------------------------


def test_focus_accuracy_matches_short_allophone_fuenf():
    # fünf is /fʏnf/ — the runtime review's B5 case
    assert word_focus_accuracy(FUENF, UE_FOCUS) == 40.0


def test_focus_accuracy_matches_long_allophone_tuer():
    # Tür is /tyːɐ̯/ — length mark must be stripped before matching
    assert word_focus_accuracy(TUER, UE_FOCUS) == 75.0


def test_focus_accuracy_none_when_no_focus_phoneme():
    assert word_focus_accuracy(MINUTEN, UE_FOCUS) is None


def test_de_focus_set_covers_both_allophones():
    assert set(FOCUS_PHONEME_SETS["de"]) == {"y", "ʏ"}


# ---- banding -------------------------------------------------------------


def test_scoreband_cuts_match_frontend():
    assert scoreband(70.0) == "good"
    assert scoreband(69.9) == "ok"
    assert scoreband(45.0) == "ok"
    assert scoreband(44.9) == "bad"


# ---- expected IPA ---------------------------------------------------------


def test_expected_ipa_joins_phonemes():
    assert expected_ipa(FUENF) == "/fʏnf/"


def test_expected_ipa_keeps_length_marks_for_display():
    assert expected_ipa(TUER) == "/tyːɐ̯/"


# ---- analyze_turn ----------------------------------------------------------


def test_analyze_turn_tokens_bands_and_focus_flags():
    analysis = analyze_turn(_response([FUENF, TUER, MINUTEN]), UE_FOCUS)
    assert [t.t for t in analysis.tokens] == ["fünf", "Tür", "Minuten"]
    assert [t.s for t in analysis.tokens] == ["ok", "good", "good"]
    assert [t.focus for t in analysis.tokens] == [True, True, False]


def test_analyze_turn_target_is_worst_focus_word():
    analysis = analyze_turn(_response([TUER, FUENF]), UE_FOCUS)
    assert analysis.target is not None
    assert analysis.target.word == "fünf"
    assert analysis.target.focus_accuracy == 40.0
    assert analysis.target.should_ipa == "/fʏnf/"


def test_analyze_turn_focus_hit_and_clear():
    # fünf's ʏ at 40 → hit but NOT clear
    a = analyze_turn(_response([FUENF, MINUTEN]), UE_FOCUS)
    assert a.focus_hit is True
    assert a.focus_clear is False
    # Tür's yː at 75 → hit AND clear
    b = analyze_turn(_response([TUER, MINUTEN]), UE_FOCUS)
    assert b.focus_hit is True
    assert b.focus_clear is True


def test_analyze_turn_no_focus_words():
    a = analyze_turn(_response([MINUTEN]), UE_FOCUS)
    assert a.focus_hit is False
    assert a.target is None
    # No focus word in the turn: nothing to judge, not "clear"
    assert a.focus_clear is False


def test_analyze_turn_empty_words_means_no_tokens():
    a = analyze_turn(_response([], text=""), UE_FOCUS)
    assert a.tokens == []
    assert a.target is None
