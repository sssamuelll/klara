import pytest

from klara.services.story_gen import StoryGenerationError, _extract_json


def test_extract_json_plain_object():
    assert _extract_json('{"title": "Hallo"}') == {"title": "Hallo"}


def test_extract_json_strips_code_fence():
    assert _extract_json('```json\n{"title": "Hallo"}\n```') == {"title": "Hallo"}


def test_extract_json_ignores_prose_around_object():
    assert _extract_json('Sure!\n{"a": 1}\nDone.') == {"a": 1}


def test_extract_json_repairs_trailing_comma():
    # The story model (DeepSeek V4 Flash) occasionally emits a trailing comma;
    # the repair fallback recovers it instead of forcing an LLM retry.
    assert _extract_json('{"a": 1, "b": [2, 3,],}') == {"a": 1, "b": [2, 3]}


def test_extract_json_repairs_single_quoted_keys():
    assert _extract_json("{'title': 'Hallo', 'n': 3}") == {"title": "Hallo", "n": 3}


def test_extract_json_repairs_missing_comma_between_pairs():
    assert _extract_json('{"a": 1 "b": 2}') == {"a": 1, "b": 2}


def test_extract_json_valid_object_skips_repair():
    # Well-formed JSON must parse via the strict path unchanged (the repair
    # fallback only runs after json.loads raises).
    assert _extract_json('{"title": "x", "sentences": [{"target": "Hallo"}]}') == {
        "title": "x",
        "sentences": [{"target": "Hallo"}],
    }


def test_extract_json_unrecoverable_raises_story_error():
    # Braces present but no recoverable object -> must still surface as
    # StoryGenerationError, never a raw json.JSONDecodeError (which 500s).
    with pytest.raises(StoryGenerationError):
        _extract_json("{ @#$%^ &*( }")


def test_extract_json_no_object_raises_story_error():
    with pytest.raises(StoryGenerationError):
        _extract_json("no json here at all")
