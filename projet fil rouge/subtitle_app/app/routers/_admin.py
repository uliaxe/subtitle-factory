from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app import cruds, services
from app.core import get_db
from app.schemas import AdminStats, JobDetail, UserCreate, UserOut

router = APIRouter(dependencies=[Depends(services.require_admin)])


@router.get("/stats", response_model=AdminStats)
def stats_route(db: Session = Depends(get_db)):
    return services.compute_stats(db)


@router.get("/jobs", response_model=list[JobDetail])
def history_route(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return cruds.list_jobs(db, limit=limit, offset=offset)


@router.get("/users", response_model=list[UserOut])
def list_users_route(db: Session = Depends(get_db)):
    return cruds.list_users(db)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user_route(payload: UserCreate, db: Session = Depends(get_db)):
    return services.register_user(db, payload)
