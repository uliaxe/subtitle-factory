import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import cruds
from app.core import SETTINGS, SessionLocal
from app.ressources import get_ai_client
from app.schemas import ALLOWED_OUTPUTS, EXTENSION_TO_KIND, InputKind, JobStatus, OutputType, Role

LOGGER = logging.getLogger(__name__)
_CHUNK_SIZE = 1024 * 1024


def detect_input_kind(filename: str) -> InputKind:
    kind = EXTENSION_TO_KIND.get(Path(filename).suffix.lower())
    if kind is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Format non pris en charge : envoyez une vidéo .mp4 ou un audio .wav"
        )
    return kind


def check_output_allowed(kind: InputKind, output_type: OutputType) -> None:
    if output_type not in ALLOWED_OUTPUTS[kind]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Un fichier audio ne peut produire que des sous-titres ou du texte",
        )


def _save_upload(source: BinaryIO, destination: Path) -> None:
    max_bytes = SETTINGS.max_upload_mb * 1024 * 1024
    written = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as target:
        while chunk := source.read(_CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                target.close()
                shutil.rmtree(destination.parent, ignore_errors=True)
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"Fichier trop volumineux (maximum {SETTINGS.max_upload_mb} Mo)",
                )
            target.write(chunk)


def create_job(
    db: Session, user: cruds.User, filename: str, source: BinaryIO, output_type: OutputType
) -> cruds.Job:
    kind = detect_input_kind(filename)
    check_output_allowed(kind, output_type)
    if cruds.count_unfinished(db) >= SETTINGS.max_concurrent_jobs:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Capacité atteinte ({SETTINGS.max_concurrent_jobs} traitements en cours). Réessayez dans quelques minutes.",
        )

    job_id = uuid.uuid4().hex
    input_path = SETTINGS.storage_dir / job_id / f"input{Path(filename).suffix.lower()}"
    _save_upload(source, input_path)
    job = cruds.Job(
        id=job_id,
        user_id=user.id,
        original_filename=Path(filename).name,
        input_kind=kind.value,
        output_type=output_type.value,
        status=JobStatus.PENDING.value,
        input_path=str(input_path),
    )
    return cruds.add_job(db, job)


def run_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = cruds.get_job(db, job_id)
        job.status = JobStatus.PROCESSING.value
        job.started_at = cruds.utcnow()
        db.commit()

        started = time.perf_counter()
        try:
            result = get_ai_client().process(
                Path(job.input_path),
                InputKind(job.input_kind),
                OutputType(job.output_type),
                Path(job.input_path).parent,
            )
        except Exception as error:
            LOGGER.exception("Échec du traitement %s", job_id)
            job.status = JobStatus.FAILED.value
            job.error_message = str(error) or error.__class__.__name__
        else:
            job.status = JobStatus.DONE.value
            job.result_text = result.text
            job.output_path = str(result.output_path)
            job.media_duration_s = result.media_duration_s
        job.processing_time_s = round(time.perf_counter() - started, 3)
        job.finished_at = cruds.utcnow()
        db.commit()


def get_visible_job(db: Session, user: cruds.User, job_id: str) -> cruds.Job:
    job = cruds.get_job(db, job_id)
    if job is None or (job.user_id != user.id and user.role != Role.ADMIN.value):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Traitement introuvable")
    return job


def get_result_path(job: cruds.Job) -> Path:
    if job.files_purged:
        raise HTTPException(status.HTTP_410_GONE, "Les fichiers de ce traitement ont été supprimés")
    if job.status != JobStatus.DONE.value or job.output_path is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Le traitement n'est pas terminé")
    return Path(job.output_path)


def delete_job_files(db: Session, job: cruds.Job) -> None:
    if job.status in (JobStatus.PENDING.value, JobStatus.PROCESSING.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "Attendez la fin du traitement")
    shutil.rmtree(Path(job.input_path).parent, ignore_errors=True)
    job.files_purged = True
    db.commit()
