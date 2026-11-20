from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(10), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    user: Mapped[User] = relationship(lazy="joined")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    input_kind: Mapped[str] = mapped_column(String(10))
    output_type: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(12), index=True, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    media_duration_s: Mapped[float | None] = mapped_column(Float)
    processing_time_s: Mapped[float | None] = mapped_column(Float)
    result_text: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    input_path: Mapped[str] = mapped_column(String(500))
    output_path: Mapped[str | None] = mapped_column(String(500))
    files_purged: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(lazy="joined")

    @property
    def username(self) -> str:
        return self.user.username
