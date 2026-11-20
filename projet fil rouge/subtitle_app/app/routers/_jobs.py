from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import cruds, services
from app.core import get_db
from app.schemas import JobDetail, JobOut, OutputType

router = APIRouter()


@router.post("", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_job_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_type: OutputType = Form(...),
    user: cruds.User = Depends(services.get_current_user),
    db: Session = Depends(get_db),
):
    job = services.create_job(db, user, file.filename or "", file.file, output_type)
    background_tasks.add_task(services.run_job, job.id)
    return job


@router.get("", response_model=list[JobOut])
def list_my_jobs_route(
    user: cruds.User = Depends(services.get_current_user), db: Session = Depends(get_db)
):
    return cruds.list_jobs(db, user_id=user.id)


@router.get("/{job_id}", response_model=JobDetail)
def get_job_route(
    job_id: str, user: cruds.User = Depends(services.get_current_user), db: Session = Depends(get_db)
):
    return services.get_visible_job(db, user, job_id)


@router.get("/{job_id}/result")
def download_result_route(
    job_id: str, user: cruds.User = Depends(services.get_current_user), db: Session = Depends(get_db)
):
    job = services.get_visible_job(db, user, job_id)
    path = services.get_result_path(job)
    stem = job.original_filename.rsplit(".", 1)[0]
    return FileResponse(path, filename=f"{stem}_{path.name}")


@router.delete("/{job_id}/files", response_model=JobOut)
def delete_files_route(
    job_id: str, user: cruds.User = Depends(services.get_current_user), db: Session = Depends(get_db)
):
    job = services.get_visible_job(db, user, job_id)
    services.delete_job_files(db, job)
    return job
