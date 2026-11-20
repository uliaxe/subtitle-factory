from app.subtitles import build_srt, build_text, format_srt_time


def test_srt_time_is_zero_padded():
    assert format_srt_time(65) == "00:01:05,000"
    assert format_srt_time(3723.4567) == "01:02:03,457"
    assert format_srt_time(-0.01) == "00:00:00,000"


def test_build_srt_numbers_blocks_from_one():
    srt = build_srt([(0.0, 1.5, "Hello."), (1.5, 3.0, "World.")])
    assert srt == "1\n00:00:00,000 --> 00:00:01,500\nHello.\n\n2\n00:00:01,500 --> 00:00:03,000\nWorld.\n"


def test_build_text_has_no_timestamps():
    assert build_text([(0.0, 1.0, "Hello."), (1.0, 2.0, ""), (2.0, 3.0, "World.")]) == "Hello. World."
