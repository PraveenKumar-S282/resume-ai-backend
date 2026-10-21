from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "mysql+pymysql://resume_user:change_me@localhost:3306/resume_ai?charset=utf8mb4"

    SECRET_KEY: str = "dev-only-change-me"
    ALGORITHM: str = "HS256"
    BCRYPT_ROUNDS: int = 12  # lowered only in tests
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    CORS_ORIGINS: str = "http://localhost:5173"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    LLM_TIMEOUT_SECONDS: int = 60

    RATE_LIMIT_ENABLED: bool = True

    @field_validator("COOKIE_SAMESITE")
    @classmethod
    def _samesite(cls, v: str) -> str:
        v = v.lower()
        if v not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be lax, strict or none")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
