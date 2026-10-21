from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Keyed by client IP. Behind a reverse proxy, run uvicorn with --proxy-headers so the real IP is used.
limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)

AUTH_LIMIT = "10/minute"
GENERATION_LIMIT = "15/minute"
