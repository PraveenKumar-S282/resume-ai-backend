import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel


def _check_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Use at least 8 characters.")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password is too long (72 bytes maximum).")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"[0-9]", v):
        raise ValueError("Include at least one letter and one number.")
    return v


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str

    _pw = field_validator("password")(_check_password)

    @field_validator("full_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str

    _pw = field_validator("new_password")(_check_password)
