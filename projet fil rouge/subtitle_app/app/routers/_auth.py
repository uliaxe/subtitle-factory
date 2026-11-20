from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import cruds, services
from app.core import get_db
from app.schemas import Role, SignUp, Token, UserCreate, UserOut

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_route(payload: SignUp, db: Session = Depends(get_db)):
    services.register_user(db, UserCreate(**payload.model_dump(), role=Role.USER))
    return services.login(db, payload.username, payload.password)


@router.post("/login", response_model=Token)
def login_route(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return services.login(db, form.username, form.password)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_route(token: str = Depends(services.OAUTH2_SCHEME), db: Session = Depends(get_db)):
    services.logout(db, token)


@router.get("/me", response_model=UserOut)
def me_route(user: cruds.User = Depends(services.get_current_user)):
    return user
