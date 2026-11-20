import json
import subprocess

from app import media
from app.subtitles import build_srt


def _streams(path) -> list[str]:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                          "-of", "json", str(path)], capture_output=True, check=True)
    return [s["codec_type"] for s in json.loads(out.stdout)["streams"]]


def _write_srt(directory):
    srt = directory / "subtitles.srt"
    srt.write_text(build_srt([(0.0, 2.0, "Hello")]), encoding="utf-8")
    return srt


def test_load_audio_gives_16khz_mono(media_dir):
    audio = media.load_audio(media_dir / "sample.mp4")
    assert abs(len(audio) / media.SAMPLE_RATE - 3.0) < 0.1


def test_probe_duration(media_dir):
    assert abs(media.probe_duration(media_dir / "sample.wav") - 3.0) < 0.1
    assert media.probe_duration(media_dir / "absent.mp4") is None


def test_burn_subtitles_with_cpu_encoder(media_dir, tmp_path):
    output = tmp_path / "burned.mp4"
    used = media.burn_subtitles(media_dir / "sample.mp4", _write_srt(tmp_path), output, encoder="cpu")
    assert used == "cpu"
    assert _streams(output) == ["video", "audio"]


def test_add_subtitle_track_keeps_video_and_adds_subtitles(media_dir, tmp_path):
    output = tmp_path / "with_track.mp4"
    media.add_subtitle_track(media_dir / "sample.mp4", _write_srt(tmp_path), output)
    assert sorted(_streams(output)) == ["audio", "subtitle", "video"]
