from app.pipeline import _scene_durations, _spoken_text, _srt_time, _wrap_caption


def test_srt_time():
    assert _srt_time(0) == "00:00:00,000"
    assert _srt_time(65.125) == "00:01:05,125"


def test_spoken_text_expands_common_abbreviation():
    assert _spoken_text("AI ช่วย OPD") == "เอไอ ช่วย โอพีดี"


def test_wrap_caption_limits_each_card_to_two_short_lines():
    cards = _wrap_caption("เอไอช่วยลดเวลารอคอยของผู้ป่วยและช่วยให้บุคลากรทำงานได้เร็วขึ้น")
    assert len(cards) >= 2
    assert all(len(card.splitlines()) <= 2 for card in cards)
    assert all(len(line) <= 24 for card in cards for line in card.splitlines())
    assert not any(line.endswith("บุคล") for card in cards for line in card.splitlines())


def test_scene_durations_follow_narration_weight():
    data = {"scenes": [{"narration": "สั้น"}, {"narration": "ประโยคนี้ยาวกว่าประโยคแรกมาก"}]}
    durations = _scene_durations(data, 30)
    assert sum(durations) == 30
    assert durations[1] > durations[0]
