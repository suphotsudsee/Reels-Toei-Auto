from app.pipeline import _srt_time


def test_srt_time():
    assert _srt_time(0) == "00:00:00,000"
    assert _srt_time(65.125) == "00:01:05,125"

