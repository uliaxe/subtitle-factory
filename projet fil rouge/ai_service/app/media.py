import logging
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

LOGGER = logging.getLogger(__name__)
SAMPLE_RATE = 16_000

_ENCODER_ARGS = {
    "nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"],
    "cpu": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"],
}


class MediaError(RuntimeError):
    pass


def _run(command: list[str], cwd: Path | None = None) -> bytes:
    completed = subprocess.run(command, cwd=cwd, capture_output=True)
    if completed.returncode != 0:
        details = completed.stderr.decode(errors="replace").strip().splitlines()[-3:]
        raise MediaError(f"{command[0]} a échoué : {' | '.join(details)}")
    return completed.stdout


def probe_duration(path: Path) -> float | None:
    try:
        out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
        return float(out.strip())
    except (MediaError, ValueError):
        return None


def load_audio(path: Path) -> np.ndarray:
    out = _run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"])
    return np.frombuffer(out, dtype=np.float32)


@lru_cache
def nvenc_available() -> bool:
    try:
        return b"h264_nvenc" in _run(["ffmpeg", "-hide_banner", "-encoders"])
    except (MediaError, FileNotFoundError):
        return False


def burn_subtitles(video: Path, srt: Path, output: Path, encoder: str = "auto") -> str:
    candidates = {"auto": ["nvenc", "cpu"] if nvenc_available() else ["cpu"],
                  "nvenc": ["nvenc"], "cpu": ["cpu"]}[encoder]
    for index, name in enumerate(candidates):
        command = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(video.resolve()),
                   "-vf", f"subtitles={srt.name}", *_ENCODER_ARGS[name],
                   "-c:a", "copy", "-movflags", "+faststart", str(output.resolve())]
        try:
            _run(command, cwd=srt.parent)
            return name
        except MediaError:
            if index == len(candidates) - 1:
                raise
            LOGGER.warning("Encodeur %s indisponible, repli sur %s", name, candidates[index + 1])
    raise AssertionError("inatteignable")


def add_subtitle_track(video: Path, srt: Path, output: Path) -> None:
    _run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(video), "-i", str(srt),
          "-map", "0:v", "-map", "0:a?", "-map", "1", "-c", "copy", "-c:s", "mov_text",
          "-metadata:s:s:0", "language=eng", "-metadata:s:s:0", "title=English",
          "-movflags", "+faststart", str(output)])
