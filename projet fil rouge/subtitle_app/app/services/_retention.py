import asyncio
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app import cruds
from app.core import SETTINGS, SessionLocal

LOGGER = logging.getLogger(__name__)


def purge_expired_files(db: Session, now: datetime | None = None) -> int:
    cutoff = (now or cruds.utcnow()) - timedelta(days=SETTINGS.retention_days)
    expired = cruds.jobs_with_files_older_than(db, cutoff)
    for job in expired:
        shutil.rmtree(Path(job.input_path).parent, ignore_errors=True)
        job.files_purged = True
    db.commit()
    return len(expired)


async def purge_periodically() -> None:
    while True:
        with SessionLocal() as db:
            purged = await asyncio.to_thread(purge_expired_files, db)
        if purged:
            LOGGER.info("%d traitement(s) purgé(s)", purged)
        await asyncio.sleep(SETTINGS.purge_interval_s)
