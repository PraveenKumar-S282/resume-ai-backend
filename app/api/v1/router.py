from fastapi import APIRouter

from app.api.v1 import analyses, auth, cover_letters, documents, profile, resumes

api_router = APIRouter()
for module in (auth, profile, analyses, resumes, cover_letters, documents):
    api_router.include_router(module.router)


@api_router.get("/health", tags=["health"], summary="Liveness check")
def health():
    return {"status": "ok"}
