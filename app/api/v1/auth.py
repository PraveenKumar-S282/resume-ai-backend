from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.errors import AppError
from app.core.rate_limit import AUTH_LIMIT, limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import CandidateProfile, User
from app.schemas.auth import ChangePasswordIn, LoginIn, RegisterIn, UserOut, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


def _email_taken(db: Session, email: str, exclude_id: int | None = None) -> bool:
    q = select(User.id).where(func.lower(User.email) == email.lower())
    if exclude_id:
        q = q.where(User.id != exclude_id)
    return db.scalar(q) is not None


def _cookie_kwargs() -> dict:
    return dict(key=settings.COOKIE_NAME, httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path="/")


@router.post("/register", response_model=UserOut, status_code=201, summary="Create an account")
@limiter.limit(AUTH_LIMIT)
def register(request: Request, data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if _email_taken(db, email):
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    user = User(email=email, full_name=data.full_name, password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    db.add(CandidateProfile(user_id=user.id, achievements=[]))
    db.commit()
    return user


@router.post("/login", response_model=UserOut, summary="Log in (sets an HttpOnly cookie)")
@limiter.limit(AUTH_LIMIT)
def login(request: Request, response: Response, data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    ok = verify_password(data.password, user.password_hash if user else None)
    if not user or not ok or not user.is_active:
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password.")
    response.set_cookie(value=create_access_token(user.id), max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **_cookie_kwargs())
    return user


@router.post("/logout", status_code=204, summary="Log out (clears the cookie)")
def logout(response: Response):
    response.delete_cookie(**{k: v for k, v in _cookie_kwargs().items() if k != "key"}, key=settings.COOKIE_NAME)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut, summary="Current user")
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut, summary="Update name or email")
def update_me(data: UserUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if data.email and data.email.lower() != user.email:
        if _email_taken(db, data.email, exclude_id=user.id):
            raise AppError(409, "EMAIL_TAKEN", "That email is already in use.")
        user.email = data.email.lower()
    if data.full_name:
        user.full_name = data.full_name.strip()
    db.commit()
    return user


@router.post("/change-password", status_code=204, summary="Change password")
def change_password(data: ChangePasswordIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(data.current_password, user.password_hash):
        raise AppError(400, "INVALID_PASSWORD", "Current password is incorrect.")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return Response(status_code=204)


@router.delete("/me", status_code=204, summary="Delete the account and all data")
def delete_me(response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(user)
    db.commit()
    response.delete_cookie(key=settings.COOKIE_NAME, path="/")
    response.status_code = 204
    return response
