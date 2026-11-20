from pydantic import BaseModel

from ._job import OutputType


class TypeStats(BaseModel):
    total: int = 0
    done: int = 0
    unfinished: int = 0
    failed: int = 0
    avg_processing_s: float | None = None


class AdminStats(BaseModel):
    total: int
    done: int
    unfinished: int
    failed: int
    avg_processing_s: float | None
    avg_realtime_ratio: float | None
    by_type: dict[OutputType, TypeStats]
