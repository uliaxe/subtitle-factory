import os
from dataclasses import dataclass
from pathlib import Path

from starlette.config import Config

TRANSCRIBERS = ("whisper", "fake")
VIDEO_ENCODERS = ("auto", "nvenc", "cpu")


@dataclass(frozen=True)
class Settings:
    transcriber: str
    model_name: str
    device: str
    compute_type: str
    beam_size: int
    num_workers: int
    video_encoder: str
    work_dir: Path
    result_ttl_hours: int


def load_settings() -> Settings:
    env = Config(".env") if os.path.isfile(".env") else Config()
    settings = Settings(
        transcriber=env("TRANSCRIBER", default="whisper"),
        model_name=env("WHISPER_MODEL", default="medium.en"),
        device=env("WHISPER_DEVICE", default="cuda"),
        compute_type=env("WHISPER_COMPUTE_TYPE", default="int8_float16"),
        beam_size=env("WHISPER_BEAM_SIZE", cast=int, default=5),
        num_workers=env("NUM_WORKERS", cast=int, default=2),
        video_encoder=env("VIDEO_ENCODER", default="auto"),
        work_dir=Path(env("WORK_DIR", default="./work")),
        result_ttl_hours=env("RESULT_TTL_HOURS", cast=int, default=24),
    )
    if settings.transcriber not in TRANSCRIBERS:
        raise ValueError(f"TRANSCRIBER doit valoir {TRANSCRIBERS}, pas {settings.transcriber!r}")
    if settings.video_encoder not in VIDEO_ENCODERS:
        raise ValueError(f"VIDEO_ENCODER doit valoir {VIDEO_ENCODERS}, pas {settings.video_encoder!r}")
    if settings.num_workers < 1 or settings.beam_size < 1:
        raise ValueError("NUM_WORKERS et WHISPER_BEAM_SIZE doivent être >= 1")
    return settings
