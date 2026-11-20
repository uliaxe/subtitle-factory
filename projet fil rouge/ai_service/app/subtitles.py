Segment = tuple[float, float, str]


def format_srt_time(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_srt(segments: list[Segment]) -> str:
    blocks = [
        f"{index}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(segments, start=1)
    ]
    return "\n".join(blocks)


def build_text(segments: list[Segment]) -> str:
    return " ".join(text for _, _, text in segments if text)
