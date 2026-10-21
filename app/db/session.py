from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def make_engine(url: str | None = None, **kwargs):
    url = url or settings.DATABASE_URL
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False}, **kwargs)

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless enabled
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
