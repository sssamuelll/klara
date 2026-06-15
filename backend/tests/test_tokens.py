"""El tokenizador canónico debe tratar comillas tipográficas y guillemets como
puntuación (NO como parte de la palabra), igual en todo el repo. Este test ancla
ese comportamiento para que el frontend pueda espejarlo byte a byte (spec §6.2)."""

from klara.services.tokens import BAND_RANK, word_tokens_by_index, worst_band

# Comillas tipográficas alemanas por codepoint, para que el fixture no dependa
# de la codificación del editor (U+201E apertura, U+201D cierre).
_OPEN_QUOTE = "„"  # „
_CLOSE_QUOTE = "”"  # ”
_LEFT_QUOTE = "“"  # “


def test_curly_quotes_are_punctuation_not_word_chars():
    # „Tür” con comillas tipográficas: la palabra es "Tür", sin las comillas.
    text = f"{_OPEN_QUOTE}Tür{_CLOSE_QUOTE} sagt sie."
    tokens = word_tokens_by_index(text)
    assert "Tür" in tokens.values()
    assert not any(
        _OPEN_QUOTE in w or _LEFT_QUOTE in w or _CLOSE_QUOTE in w for w in tokens.values()
    )


def test_word_indices_are_global_token_positions():
    # "Die Nummer" -> word tokens en índices globales 0 y 2 (1 es el espacio).
    tokens = word_tokens_by_index("Die Nummer")
    assert tokens == {0: "Die", 2: "Nummer"}


def test_worst_band_picks_lowest_rank():
    assert worst_band({0: "good", 2: "bad", 4: "ok"}) == "bad"
    assert worst_band({0: "good", 2: "ok"}) == "ok"
    assert worst_band({}) is None
    assert BAND_RANK["bad"] < BAND_RANK["ok"] < BAND_RANK["good"]
