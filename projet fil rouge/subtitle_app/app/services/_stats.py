from statistics import mean

from sqlalchemy.orm import Session

from app import cruds
from app.schemas import UNFINISHED_STATUSES, AdminStats, JobStatus, OutputType, TypeStats

_UNFINISHED = {s.value for s in UNFINISHED_STATUSES}


def _average(values: list[float]) -> float | None:
    return round(mean(values), 3) if values else None


def compute_stats(db: Session) -> AdminStats:
    jobs = cruds.all_jobs(db)
    by_type = {output_type: TypeStats() for output_type in OutputType}
    times_by_type: dict[OutputType, list[float]] = {output_type: [] for output_type in OutputType}
    ratios: list[float] = []

    for job in jobs:
        output_type = OutputType(job.output_type)
        stats = by_type[output_type]
        stats.total += 1
        if job.status == JobStatus.DONE.value:
            stats.done += 1
            times_by_type[output_type].append(job.processing_time_s)
            if job.media_duration_s:
                ratios.append(job.processing_time_s / job.media_duration_s)
        elif job.status == JobStatus.FAILED.value:
            stats.failed += 1
        elif job.status in _UNFINISHED:
            stats.unfinished += 1

    for output_type, stats in by_type.items():
        stats.avg_processing_s = _average(times_by_type[output_type])

    return AdminStats(
        total=len(jobs),
        done=sum(s.done for s in by_type.values()),
        unfinished=sum(s.unfinished for s in by_type.values()),
        failed=sum(s.failed for s in by_type.values()),
        avg_processing_s=_average([t for times in times_by_type.values() for t in times]),
        avg_realtime_ratio=_average(ratios),
        by_type=by_type,
    )
