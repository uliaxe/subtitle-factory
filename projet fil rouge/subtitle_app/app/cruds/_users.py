from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ._models import AuthToken, User, utcnow


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)))


def count_users(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User))


def create_user(db: Session, username: str, password_hash: str, role: str) -> User:
    user = User(username=username, password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    return user


def create_token(db: Session, token: str, user_id: int, expires_at: datetime) -> AuthToken:
    auth_token = AuthToken(token=token, user_id=user_id, expires_at=expires_at)
    db.add(auth_token)
    db.commit()
    return auth_token


def get_valid_token(db: Session, token: str) -> AuthToken | None:
    return db.scalar(
        select(AuthToken).where(AuthToken.token == token, AuthToken.expires_at > utcnow())
    )


def delete_token(db: Session, token: str) -> None:
    db.execute(delete(AuthToken).where(AuthToken.token == token))
    db.commit()
