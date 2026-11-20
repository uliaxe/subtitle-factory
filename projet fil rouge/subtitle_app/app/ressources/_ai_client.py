import shutil
import subprocess
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import httpx

from app.core import SETTINGS
from app.schemas import InputKind, OutputType

OUTPUT_FILENAMES = {
    OutputType.TEXT: "transcript.txt",
    OutputType.SUBTITLES: "subtitles.srt",
    OutputType.VIDEO_EMBEDDED: "video_sous_titree.mp4",
    OutputType.VIDEO_METADATA: "video_piste_sous_titres.mp4",
}


@dataclass(frozen=True)
class AIResult:
    text: str
    output_path: Path
    media_duration_s: float | None


class AIClient(Protocol):
    def process(
        self, input_path: Path, input_kind: InputKind, output_type: OutputType, output_dir: Path
    ) -> AIResult:
        pass


def format_srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_srt(segments: list[tuple[float, float, str]]) -> str:
    blocks = [
        f"{index}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(segments, start=1)
    ]
    return "\n".join(blocks)


def probe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return float(completed.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        return None


_DEMO_SENTENCES = [
    "This is a demonstration transcript.",
    "The real transcription will come from the Whisper service on the GPU server.",
    "Each line is a subtitle segment with its own timestamps.",
    "The application stores this text in the history for the administrator.",
]


class FakeAIClient:
    def __init__(self, delay_s: float):
        self._delay_s = delay_s

    def process(
        self, input_path: Path, input_kind: InputKind, output_type: OutputType, output_dir: Path
    ) -> AIResult:
        time.sleep(self._delay_s)
        segments = [(i * 3.0, i * 3.0 + 2.8, s) for i, s in enumerate(_DEMO_SENTENCES)]
        text = " ".join(s for _, _, s in segments)
        output_path = output_dir / OUTPUT_FILENAMES[output_type]

        if output_type is OutputType.TEXT:
            output_path.write_text(text, encoding="utf-8", newline="\n")
        elif output_type is OutputType.SUBTITLES:
            output_path.write_text(build_srt(segments), encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(input_path, output_path)

        return AIResult(text=text, output_path=output_path, media_duration_s=probe_duration(input_path))


class AIServiceError(RuntimeError):
    pass


class HttpAIClient:
    def __init__(self, base_url: str, timeout_s: float, transport: httpx.BaseTransport | None = None):
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_s, connect=10.0)
        self._transport = transport

    def process(
        self, input_path: Path, input_kind: InputKind, output_type: OutputType, output_dir: Path
    ) -> AIResult:
        try:
            with httpx.Client(base_url=self._base_url, timeout=self._timeout, transport=self._transport) as http:
                with input_path.open("rb") as media:
                    response = http.post(
                        "/v1/jobs",
                        files={"file": (input_path.name, media)},
                        data={"output_type": output_type.value},
                    )
                _check(response)
                body = response.json()
                output_path = output_dir / OUTPUT_FILENAMES[output_type]
                try:
                    self._download(http, f"/v1/jobs/{body['job_id']}/files/{body['output_filename']}", output_path)
                finally:
                    http.delete(f"/v1/jobs/{body['job_id']}")
        except httpx.TimeoutException as error:
            raise AIServiceError("Le service IA n'a pas répondu à temps") from error
        except httpx.TransportError as error:
            raise AIServiceError(f"Service IA injoignable ({self._base_url})") from error

        return AIResult(text=body["text"], output_path=output_path, media_duration_s=body["media_duration_s"])

    @staticmethod
    def _download(http: httpx.Client, url: str, destination: Path) -> None:
        with http.stream("GET", url) as response:
            _check(response)
            with destination.open("wb") as target:
                for chunk in response.iter_bytes(1024 * 1024):
                    target.write(chunk)


def _check(response: httpx.Response) -> None:
    if response.is_success:
        return
    if response.status_code == 429:
        raise AIServiceError("Service IA saturé : tous ses workers sont occupés")
    response.read()
    try:
        detail = response.json().get("detail", "")
    except ValueError:
        detail = response.text[:200]
    raise AIServiceError(f"Service IA : erreur {response.status_code} {detail}".strip())


@lru_cache
def get_ai_client() -> AIClient:
    if SETTINGS.ai_backend == "http":
        return HttpAIClient(SETTINGS.ai_service_url, SETTINGS.ai_timeout_s)
    return FakeAIClient(delay_s=SETTINGS.fake_ai_delay_s)
