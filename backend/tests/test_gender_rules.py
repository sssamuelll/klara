"""Pure gender-suffix detector + oracle reconciliation (no DB, no async)."""

from klara.curriculum.gender_rules import (
    detect_gender_rule,
    reconcile_rule,
)


def test_detect_hard_suffixes_map_to_article_and_class():
    cases = {
        "Wohnung": ("ung", "die"),
        "Mädchen": ("chen", "das"),
        "Häuslein": ("lein", "das"),
        "Freiheit": ("heit", "die"),
        "Möglichkeit": ("keit", "die"),
        "Mannschaft": ("schaft", "die"),
        "Nation": ("tion", "die"),
        "Lehrling": ("ling", "der"),
        "Kapitalismus": ("ismus", "der"),
        "Dokument": ("ment", "das"),
        "Reichtum": ("tum", "das"),
    }
    for lemma, (suffix, gender) in cases.items():
        r = detect_gender_rule(lemma)
        assert r is not None, lemma
        assert (r.suffix, r.rule_gender, r.suffix_class) == (suffix, gender, "hard"), lemma


def test_detect_longest_match_wins():
    # -ität (4) beats -tät (3); both → die, but the longer suffix is reported.
    assert detect_gender_rule("Universität").suffix == "ität"


def test_detect_tendency_suffixes():
    r = detect_gender_rule("Mutter")  # the classic -er trap
    assert (r.rule_gender, r.suffix_class) == ("der", "tendency")
    assert detect_gender_rule("Blume").suffix_class == "tendency"  # -e → die (tendency)


def test_detect_none_when_no_suffix_or_stem_too_short():
    assert detect_gender_rule("Tisch") is None  # no matching suffix
    assert detect_gender_rule("xe") is None  # -e matches but stem "x" < 2 codepoints
    assert detect_gender_rule("") is None


def test_detect_nis_is_excluded():
    # -nis is genuinely two-gendered (die/das) → not a detector rule at all.
    assert detect_gender_rule("Ergebnis") is None
    assert detect_gender_rule("Erlaubnis") is None


def test_detect_schwung_still_detects_ung():
    # The detector is deliberately simple — Schwung detects -ung; suppression is
    # the reconciler's job (Case B), not the detector's.
    assert detect_gender_rule("Schwung").rule_gender == "die"


def test_reconcile_case_a_agreement():
    rule = detect_gender_rule("Wohnung")  # -ung → die
    d = reconcile_rule(rule, "die", "Wohnung")
    assert d == {
        "suffix": "ung",
        "suffix_class": "hard",
        "rule_gender": "die",
        "oracle_gender": "die",
        "agreement": True,
        "is_exception": False,
    }


def test_reconcile_case_b_tendency_disagrees_is_the_invariant():
    # -er → der but oracle die (die Mutter): disagreement, NOT curated → suppress.
    rule = detect_gender_rule("Mutter")
    d = reconcile_rule(rule, "die", "Mutter")
    assert d["agreement"] is False and d["is_exception"] is False


def test_reconcile_case_b_hard_false_positive():
    rule = detect_gender_rule("Schwung")  # -ung → die
    d = reconcile_rule(rule, "der", "Schwung")
    assert d["agreement"] is False and d["is_exception"] is False


def test_reconcile_case_c_curated_exception():
    rule = detect_gender_rule("Reichtum")  # -tum → das
    d = reconcile_rule(rule, "der", "Reichtum")  # oracle der; curated der
    assert d["agreement"] is False and d["is_exception"] is True


def test_reconcile_curated_only_when_value_matches_oracle():
    # Reichtum is curated 'der'; a nonsensical oracle 'die' must NOT be treated
    # as a curated exception (cross-check) → falls to Case B.
    rule = detect_gender_rule("Reichtum")
    d = reconcile_rule(rule, "die", "Reichtum")
    assert d["agreement"] is False and d["is_exception"] is False


def test_reconcile_uncurated_compound_falls_to_case_b():
    rule = detect_gender_rule("Privatreichtum")  # -tum → das, NOT in the curated list
    d = reconcile_rule(rule, "der", "Privatreichtum")
    assert d["agreement"] is False and d["is_exception"] is False
