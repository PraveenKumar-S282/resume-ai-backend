from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# bcrypt only uses the first 72 bytes; schemas reject longer passwords.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Always performs a bcrypt check so response time does not reveal whether an email exists."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), (password_hash or _DUMMY_HASH).encode()) and password_hash is not None
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
