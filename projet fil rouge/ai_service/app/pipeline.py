import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app import media
from app.subtitles import build_srt, build_text
from app.transcriber import Transcriber


class InputKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


class OutputType(str, Enum):
    VIDEO_EMBEDDED = "video_embedded"
    VIDEO_METADATA = "video_metadata"
    SUBTITLES = "subtitles"
    TEXT = "text"


EXTENSION_TO_KIND = {".mp4": InputKind.VIDEO, ".wav": InputKind.AUDIO}

ALLOWED_OUTPUTS = {
    InputKind.VIDEO: set(OutputType),
    InputKind.AUDIO: {OutputType.SUBTITLES, OutputType.TEXT},
}

OUTPUT_FILENAMES = {
    OutputType.TEXT: "transcript.txt",
    OutputType.SUBTITLES: "subtitles.srt",
    OutputType.VIDEO_EMBEDDED: "video_sous_titree.mp4",
    OutputType.VIDEO_METADATA: "video_piste_sous_titres.mp4",
}


@dataclass(frozen=True)
class PipelineResult:
    text: str
    output_filename: str
    media_duration_s: float | None
    transcription_s: float
    total_s: float
    video_encoder: str | None


async def run_pipeline(
    transcriber: Transcriber, input_path: Path, output_type: OutputType, encoder: str
) -> PipelineResult:
    started = time.perf_counter()
    job_dir = input_path.parent

    segments = await transcriber.transcribe(input_path)
    transcription_s = time.perf_counter() - started

    text = build_text(segments)
    srt_path = job_dir / OUTPUT_FILENAMES[OutputType.SUBTITLES]
    srt_path.write_text(build_srt(segments), encoding="utf-8", newline="\n")
    output_path = job_dir / OUTPUT_FILENAMES[output_type]
    used_encoder = None

    if output_type is OutputType.TEXT:
        output_path.write_text(text, encoding="utf-8", newline="\n")
    elif output_type is OutputType.VIDEO_EMBEDDED:
        used_encoder = await asyncio.to_thread(media.burn_subtitles, input_path, srt_path, output_path, encoder)
    elif output_type is OutputType.VIDEO_METADATA:
        await asyncio.to_thread(media.add_subtitle_track, input_path, srt_path, output_path)

    return PipelineResult(
        text=text,
        output_filename=output_path.name,
        media_duration_s=await asyncio.to_thread(media.probe_duration, input_path),
        transcription_s=round(transcription_s, 3),
        total_s=round(time.perf_counter() - started, 3),
        video_encoder=used_encoder,
    )
