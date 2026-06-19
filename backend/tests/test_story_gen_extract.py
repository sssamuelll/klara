import pytest

from klara.services.story_gen import StoryGenerationError, _extract_json


def test_extract_json_plain_object():
    assert _extract_json('{"title": "Hallo"}') == {"title": "Hallo"}


def test_extract_json_strips_code_fence():
    assert _extract_json('```json\n{"title": "Hallo"}\n```') == {"title": "Hallo"}


def test_extract_json_ignores_prose_around_object():
    assert _extract_json('Sure!\n{"a": 1}\nDone.') == {"a": 1}


def test_extract_json_malformed_raises_story_error():
    # Trailing comma is invalid JSON -> must surface as StoryGenerationError,
    # never an unhandled json.JSONDecodeError (which 500s the request).
    with pytest.raises(StoryGenerationError):
        _extract_json('{"a": 1,}')


def test_extract_json_no_object_raises_story_error():
    with pytest.raises(StoryGenerationError):
        _extract_json("no json here at all")
