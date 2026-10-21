from typing import TypeVar

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

T = TypeVar("T")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    user_id = decode_access_token(token) if token else None
    user = db.scalar(select(User).where(User.id == user_id)) if user_id else None
    if user is None or not user.is_active:
        raise AppError(401, "UNAUTHORIZED", "Please log in to continue.")
    return user


def get_owned_or_404(db: Session, model: type[T], obj_id: int, user_id: int, label: str) -> T:
    """Foreign ids return 404 (not 403) so the existence of other users' data is not revealed."""
    obj = db.get(model, obj_id)
    if obj is None or getattr(obj, "user_id", None) != user_id:
        raise AppError(404, "NOT_FOUND", f"{label} not found.")
    return obj
