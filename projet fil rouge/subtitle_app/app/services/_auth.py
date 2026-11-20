from datetime import timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import cruds
from app.core import SETTINGS, get_db, hash_password, new_token, verify_password
from app.schemas import Role, Token, UserCreate, UserOut

OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def login(db: Session, username: str, password: str) -> Token:
    user = cruds.get_user_by_username(db, username)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiant ou mot de passe incorrect")
    expires_at = cruds.utcnow() + timedelta(hours=SETTINGS.token_ttl_hours)
    auth_token = cruds.create_token(db, new_token(), user.id, expires_at)
    return Token(access_token=auth_token.token, user=UserOut.model_validate(user))


def logout(db: Session, token: str) -> None:
    cruds.delete_token(db, token)


def get_current_user(
    token: str = Depends(OAUTH2_SCHEME), db: Session = Depends(get_db)
) -> cruds.User:
    auth_token = cruds.get_valid_token(db, token)
    if auth_token is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Session expirée, reconnectez-vous",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_token.user


def require_admin(user: cruds.User = Depends(get_current_user)) -> cruds.User:
    if user.role != Role.ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs")
    return user


def register_user(db: Session, payload: UserCreate) -> cruds.User:
    if cruds.get_user_by_username(db, payload.username) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce nom d'utilisateur existe déjà")
    return cruds.create_user(db, payload.username, hash_password(payload.password), payload.role.value)


def ensure_default_admin(db: Session) -> None:
    if cruds.count_users(db) == 0:
        cruds.create_user(
            db, SETTINGS.admin_username, hash_password(SETTINGS.admin_password), Role.ADMIN.value
        )
