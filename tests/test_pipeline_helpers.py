from pathlib import Path

from app.pipeline import _caption_chunks, _parse_srt, _srt_time


def test_srt_time():
    assert _srt_time(0) == "00:00:00,000"
    assert _srt_time(65.125) == "00:01:05,125"


def test_caption_chunks_do_not_split_english_words():
    chunks = _caption_chunks("Hospitals are using AI-powered systems")

    assert chunks == ["Hospitals are using\nAI-powered systems"]
    assert "us\ning" not in "\n".join(chunks)


def test_caption_chunks_have_at_most_two_lines():
    chunks = _caption_chunks(
        "Hospitals are using AI-powered systems to improve patient services"
    )

    assert all(len(chunk.splitlines()) <= 2 for chunk in chunks)


def test_caption_chunks_preserve_thai_text():
    text = "โรงพยาบาลใช้ปัญญาประดิษฐ์ช่วยลดเวลารอคอยของผู้ป่วย"
    chunks = _caption_chunks(text)

    assert "".join(chunks).replace("\n", "") == text


def test_parse_srt_preserves_multiline_thai(tmp_path: Path):
    srt = tmp_path / "captions.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:02,500\nภาษาไทย\nอ่านง่าย\n",
        encoding="utf-8",
    )

    assert _parse_srt(srt) == [(0.0, 2.5, "ภาษาไทย\nอ่านง่าย")]
