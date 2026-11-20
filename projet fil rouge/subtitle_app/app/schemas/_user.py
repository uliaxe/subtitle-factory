from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role
    created_at: datetime


class SignUp(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)


class UserCreate(SignUp):
    role: Role = Role.USER


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
