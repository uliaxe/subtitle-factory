import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ._config import SETTINGS
from ._database import SessionLocal, init_db


@asynccontextmanager
async def lifespan(application: FastAPI):
    from app import cruds, services

    SETTINGS.storage_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    with SessionLocal() as db:
        services.ensure_default_admin(db)
        cruds.fail_unfinished(db, "Traitement interrompu par un redémarrage du serveur")
    purge_task = asyncio.create_task(services.purge_periodically())

    yield

    purge_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await purge_task
