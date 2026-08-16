from app.pipeline import _caption_chunks, _caption_units, _srt_time


def test_srt_time():
    assert _srt_time(0) == "00:00:00,000"
    assert _srt_time(65.125) == "00:01:05,125"



def test_caption_units_keep_thai_combining_marks_together():
    units = _caption_units("ก้าว")
    assert "".join(units) == "ก้าว"
    assert any(len(unit) > 1 for unit in units)


def test_caption_chunks_fit_reels_safe_zone():
    text = "เทคโนโลยี AI ช่วยลดเวลารอคอยเฉลี่ยในแผนกฉุกเฉินและทำให้ผู้ป่วยได้รับการดูแลรวดเร็วขึ้น"
    chunks = _caption_chunks(text)

    assert len(chunks) > 1
    assert all(len(chunk.splitlines()) <= 2 for chunk in chunks)
    assert all(
        len(_caption_units(line)) <= 16
        for chunk in chunks
        for line in chunk.splitlines()
    )
    assert "".join(chunk.replace("\n", "") for chunk in chunks).replace(" ", "") == text.replace(" ", "")
