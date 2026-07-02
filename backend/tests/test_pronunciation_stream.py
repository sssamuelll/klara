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
