from fastapi import APIRouter
from sqlalchemy import text

from app.core import SETTINGS, SessionLocal

router = APIRouter()


@router.get("/healthz")
def healthcheck():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "version": SETTINGS.version}
