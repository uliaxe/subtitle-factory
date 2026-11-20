import os
from dataclasses import dataclass
from pathlib import Path

from starlette.config import Config


@dataclass(frozen=True)
class Settings:
    app_name: str
    version: str
    database_url: str
    storage_dir: Path
    retention_days: int
    purge_interval_s: int
    max_concurrent_jobs: int
    max_upload_mb: int
    token_ttl_hours: int
    ai_backend: str
    ai_service_url: str
    ai_timeout_s: float
    fake_ai_delay_s: float
    admin_username: str
    admin_password: str


def _load_settings() -> Settings:
    env = Config(".env") if os.path.isfile(".env") else Config()
    settings = Settings(
        app_name=env("APP_NAME", default="Sous-titrage"),
        version=env("APP_VERSION", default="0.1.0"),
        database_url=env("DATABASE_URL", default="sqlite:///./data/app.db"),
        storage_dir=Path(env("STORAGE_DIR", default="./data/storage")),
        retention_days=env("RETENTION_DAYS", cast=int, default=7),
        purge_interval_s=env("PURGE_INTERVAL_S", cast=int, default=3600),
        max_concurrent_jobs=env("MAX_CONCURRENT_JOBS", cast=int, default=10),
        max_upload_mb=env("MAX_UPLOAD_MB", cast=int, default=4096),
        token_ttl_hours=env("TOKEN_TTL_HOURS", cast=int, default=12),
        ai_backend=env("AI_BACKEND", default="fake"),
        ai_service_url=env("AI_SERVICE_URL", default="http://localhost:8001"),
        ai_timeout_s=env("AI_TIMEOUT_S", cast=float, default=6 * 3600),
        fake_ai_delay_s=env("FAKE_AI_DELAY_S", cast=float, default=4.0),
        admin_username=env("ADMIN_USERNAME", default="admin"),
        admin_password=env("ADMIN_PASSWORD", default="admin"),
    )
    if settings.ai_backend not in ("fake", "http"):
        raise ValueError(f"AI_BACKEND inconnu : {settings.ai_backend!r}")
    if settings.retention_days < 1 or settings.max_concurrent_jobs < 1:
        raise ValueError("RETENTION_DAYS et MAX_CONCURRENT_JOBS doivent être >= 1")
    return settings


SETTINGS = _load_settings()
