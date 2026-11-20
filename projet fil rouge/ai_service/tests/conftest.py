import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg non installé")


def make_settings(work_dir: Path, **overrides) -> Settings:
    values = dict(
        transcriber="fake", model_name="fake", device="cpu", compute_type="int8", beam_size=1,
        num_workers=2, video_encoder="cpu", work_dir=work_dir, result_ttl_hours=24,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(make_settings(tmp_path / "work"))) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def media_dir(tmp_path_factory) -> Path:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg non installé")
    directory = tmp_path_factory.mktemp("media")
    lavfi = ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=3",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=3"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *lavfi, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(directory / "sample.mp4")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    str(directory / "sample.wav")], check=True)
    return directory
