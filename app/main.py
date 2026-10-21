import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.rate_limit import limiter
from app.db.seed import seed_templates
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        with SessionLocal() as db:
            seed_templates(db)
    except Exception as exc:  # database not migrated yet; the API still starts so /docs is reachable
        log.warning("Could not seed templates (run `alembic upgrade head`?): %s", exc)
    if settings.is_production and settings.SECRET_KEY.startswith("dev-only"):
        log.error("SECRET_KEY is the development default. Set a strong SECRET_KEY before going live.")
    yield


app = FastAPI(
    title="ResumeAI API",
    description="AI-powered resume and cover letter generation. Keyword scores are estimates, not a guarantee of any ATS outcome.",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
register_error_handlers(app)


@app.middleware("http")
async def origin_check(request: Request, call_next):
    """CSRF defence for cookie auth: browsers always send Origin on cross-site unsafe requests."""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            same_origin = origin.rstrip("/") == f"{request.url.scheme}://{request.headers.get('host', '')}"
            if not same_origin and origin.rstrip("/") not in settings.cors_origin_list:
                return JSONResponse(status_code=403, content={"error": {"code": "FORBIDDEN_ORIGIN", "message": "Request origin is not allowed.", "details": []}})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "Authorization"],
)
app.include_router(api_router, prefix="/api/v1")
