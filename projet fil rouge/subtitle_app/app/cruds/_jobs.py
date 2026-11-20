from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.schemas import UNFINISHED_STATUSES, JobStatus

from ._models import Job


def add_job(db: Session, job: Job) -> Job:
    db.add(job)
    db.commit()
    return job


def get_job(db: Session, job_id: str) -> Job | None:
    return db.get(Job, job_id)


def list_jobs(db: Session, user_id: int | None = None, limit: int = 200, offset: int = 0) -> list[Job]:
    query = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    if user_id is not None:
        query = query.where(Job.user_id == user_id)
    return list(db.scalars(query))


def all_jobs(db: Session) -> list[Job]:
    return list(db.scalars(select(Job)))


def count_unfinished(db: Session) -> int:
    statuses = [s.value for s in UNFINISHED_STATUSES]
    return db.scalar(select(func.count()).select_from(Job).where(Job.status.in_(statuses)))


def fail_unfinished(db: Session, message: str) -> int:
    statuses = [s.value for s in UNFINISHED_STATUSES]
    result = db.execute(
        update(Job)
        .where(Job.status.in_(statuses))
        .values(status=JobStatus.FAILED.value, error_message=message)
    )
    db.commit()
    return result.rowcount


def jobs_with_files_older_than(db: Session, cutoff: datetime) -> list[Job]:
    return list(
        db.scalars(select(Job).where(Job.created_at < cutoff, Job.files_purged.is_(False)))
    )
