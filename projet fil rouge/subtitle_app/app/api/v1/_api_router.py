from fastapi import APIRouter

from app.routers import admin, auth, jobs

"""
Routeur de l'API v1 : enregistre les routes et leurs préfixes.
La documentation OpenAPI (/docs) est mise à jour automatiquement.
"""
API_ROUTERS = APIRouter()

API_ROUTERS.include_router(auth.router, tags=["auth"], prefix="/auth")
API_ROUTERS.include_router(jobs.router, tags=["jobs"], prefix="/jobs")
API_ROUTERS.include_router(admin.router, tags=["admin"], prefix="/admin")
