import logging
import re
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config import Settings, load_settings
from app.pipeline import ALLOWED_OUTPUTS, EXTENSION_TO_KIND, OUTPUT_FILENAMES, OutputType, run_pipeline
from app.transcriber import build_transcriber

LOGGER = logging.getLogger(__name__)
_CHUNK_SIZE = 1024 * 1024
_JOB_ID = re.compile(r"^[0-9a-f]{32}$")


def _purge_old_jobs(work_dir: Path, ttl_hours: int) -> None:
    limit = time.time() - ttl_hours * 3600
    for job_dir in work_dir.iterdir():
        if job_dir.is_dir() and job_dir.stat().st_mtime < limit:
            shutil.rmtree(job_dir, ignore_errors=True)


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.work_dir.mkdir(parents=True, exist_ok=True)
        app.state.active_jobs = 0
        app.state.transcriber = build_transcriber(settings)
        await app.state.transcriber.start()
        yield
        app.state.transcriber.stop()

    app = FastAPI(title="Service IA de sous-titrage", version="0.1.0", lifespan=lifespan)

    def job_dir(job_id: str) -> Path:
        path = settings.work_dir / job_id
        if not _JOB_ID.match(job_id) or not path.is_dir():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Traitement introuvable")
        return path

    @app.get("/healthz")
    def healthz() -> dict:
        return {
            "status": "ok",
            "transcriber": settings.transcriber,
            "model": settings.model_name,
            "workers": settings.num_workers,
            "active_jobs": app.state.active_jobs,
        }

    @app.post("/v1/jobs")
    async def create_job(file: UploadFile = File(...), output_type: OutputType = Form(...)) -> dict:
        kind = EXTENSION_TO_KIND.get(Path(file.filename or "").suffix.lower())
        if kind is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Format non pris en charge (.mp4 ou .wav)")
        if output_type not in ALLOWED_OUTPUTS[kind]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un audio ne peut produire que .srt ou texte")
        if app.state.active_jobs >= settings.num_workers:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Tous les workers sont occupés")
        app.state.active_jobs += 1

        job_id = uuid.uuid4().hex
        path = settings.work_dir / job_id
        try:
            _purge_old_jobs(settings.work_dir, settings.result_ttl_hours)
            path.mkdir()
            input_path = path / f"input{Path(file.filename).suffix.lower()}"
            with input_path.open("wb") as target:
                while chunk := await file.read(_CHUNK_SIZE):
                    target.write(chunk)
            result = await run_pipeline(app.state.transcriber, input_path, output_type, settings.video_encoder)
        except Exception as error:
            shutil.rmtree(path, ignore_errors=True)
            LOGGER.exception("Échec du traitement %s", job_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Échec du traitement : {error}") from error
        finally:
            app.state.active_jobs -= 1
        input_path.unlink(missing_ok=True)

        LOGGER.info("Traitement %s : %s en %.1f s (média %.1f s)", job_id, output_type.value,
                    result.total_s, result.media_duration_s or 0)
        return {"job_id": job_id, **result.__dict__}

    @app.get("/v1/jobs/{job_id}/files/{filename}")
    def download_file(job_id: str, filename: str) -> FileResponse:
        path = job_dir(job_id) / filename
        if filename not in OUTPUT_FILENAMES.values() or not path.is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable")
        return FileResponse(path, filename=filename)

    @app.delete("/v1/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_job(job_id: str) -> None:
        shutil.rmtree(job_dir(job_id), ignore_errors=True)

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
app = create_app(load_settings())
