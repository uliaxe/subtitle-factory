from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api.v1 import API_ROUTERS
from app.core import SETTINGS
from app.core._lifespan import lifespan
from app.routers import health

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


async def _no_cache_frontend(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def get_app() -> FastAPI:
    fast_app = FastAPI(title=SETTINGS.app_name, version=SETTINGS.version, lifespan=lifespan)
    fast_app.middleware("http")(_no_cache_frontend)
    fast_app.include_router(health.router, tags=["health"])
    fast_app.include_router(API_ROUTERS, prefix="/api/v1")
    fast_app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return fast_app


app = get_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
