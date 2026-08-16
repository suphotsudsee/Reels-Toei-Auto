import unicodedata

from app.pipeline import _caption_chunks, _caption_tokens, _srt_time


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


def test_caption_chunks_do_not_cut_thai_combining_marks():
    text = "เทคโนโลยีปัญญาประดิษฐ์ช่วยให้ผู้ป่วยได้รับบริการรวดเร็วขึ้น"
    chunks = _caption_chunks(text, max_line_width=12)

    for line in "\n".join(chunks).splitlines():
        assert line
        assert unicodedata.category(line[0]) not in {"Mn", "Me"}
    assert "".join(chunks).replace("\n", "") == text


def test_caption_chunks_keep_thai_suffix_with_previous_word():
    chunks = _caption_chunks("ผู้ป่วยได้รับบริการรวดเร็วขึ้น", max_line_width=10)

    assert not any(line == "ขึ้น" for line in "\n".join(chunks).splitlines())
    assert "".join(chunks).replace("\n", "") == "ผู้ป่วยได้รับบริการรวดเร็วขึ้น"


def test_caption_chunks_balance_lines_without_changing_english_words():
    text = "Artificial intelligence improves hospital patient services every day"
    chunks = _caption_chunks(text, max_line_width=22)

    rendered_words = " ".join(" ".join(chunks).split())
    assert rendered_words == text
    assert all(len(chunk.splitlines()) <= 2 for chunk in chunks)


def test_caption_tokens_keep_thai_and_english_content():
    text = "AI-powered ช่วยโรงพยาบาลได้จริง"

    assert "".join(_caption_tokens(text)) == text
