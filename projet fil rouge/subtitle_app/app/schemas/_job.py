from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class InputKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


class OutputType(str, Enum):
    VIDEO_EMBEDDED = "video_embedded"
    VIDEO_METADATA = "video_metadata"
    SUBTITLES = "subtitles"
    TEXT = "text"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


UNFINISHED_STATUSES = (JobStatus.PENDING, JobStatus.PROCESSING)

ALLOWED_OUTPUTS: dict[InputKind, set[OutputType]] = {
    InputKind.VIDEO: set(OutputType),
    InputKind.AUDIO: {OutputType.SUBTITLES, OutputType.TEXT},
}

EXTENSION_TO_KIND = {".mp4": InputKind.VIDEO, ".wav": InputKind.AUDIO}


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    original_filename: str
    input_kind: InputKind
    output_type: OutputType
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    media_duration_s: float | None
    processing_time_s: float | None
    error_message: str | None
    files_purged: bool


class JobDetail(JobOut):
    result_text: str | None
