from __future__ import annotations


def test_streaming_settings_defaults():
    from klara.config import Settings

    s = Settings()
    assert s.pron_stream_send_timeout_s == 5.0
    assert s.pron_stream_stop_timeout_s == 3.0
    assert s.pron_stream_ping_interval_s == 10.0
    assert s.pron_stream_pong_timeout_s == 5.0
    assert s.pron_stream_max_session_s == 90.0
    assert s.pron_stream_global_cap == 8
    assert s.pron_stream_per_user_cap == 2


def test_word_message_has_no_index():
    from klara.pronunciation.schemas import WordScore
    from klara.pronunciation.streaming import word_message

    msg = word_message(WordScore(word="Hallo", accuracy_score=91.0, error_type="None", phonemes=[]))
    assert msg == {"type": "word", "word": "Hallo", "accuracy_score": 91.0, "error_type": "None"}
    assert "index" not in msg and "offset_ms" not in msg


def test_final_message_shape():
    from klara.pronunciation.schemas import PronunciationScores, WordScore
    from klara.pronunciation.streaming import final_message

    msg = final_message(
        [WordScore(word="Hallo", accuracy_score=91.0, error_type="None", phonemes=[])],
        PronunciationScores(accuracy=90.0, fluency=88.0, completeness=100.0, pronunciation=89.0),
    )
    assert msg["type"] == "final"
    assert msg["words"][0]["word"] == "Hallo"
    assert msg["scores"]["pronunciation"] == 89.0
