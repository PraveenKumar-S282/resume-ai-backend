from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, literal, select, union_all
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import DocumentTemplate, GeneratedCoverLetter, GeneratedResume, JobAnalysis, User
from app.schemas.common import Page
from app.schemas.documents import DashboardOut, DocumentListItem, TemplateOut
from app.services.profile_service import completeness, get_or_create_profile

router = APIRouter(tags=["documents"])


def _docs_query(user_id: int, doc_type: str | None, q: str | None):
    parts = []
    if doc_type in (None, "resume"):
        s = select(literal("resume").label("type"), GeneratedResume.id.label("id"), GeneratedResume.title.label("title"),
                   GeneratedResume.status.label("status"), GeneratedResume.created_at.label("created_at")).where(GeneratedResume.user_id == user_id)
        parts.append(s.where(GeneratedResume.title.icontains(q, autoescape=True)) if q else s)
    if doc_type in (None, "cover_letter"):
        s = select(literal("cover_letter").label("type"), GeneratedCoverLetter.id.label("id"), GeneratedCoverLetter.title.label("title"),
                   GeneratedCoverLetter.status.label("status"), GeneratedCoverLetter.created_at.label("created_at")).where(GeneratedCoverLetter.user_id == user_id)
        parts.append(s.where(GeneratedCoverLetter.title.icontains(q, autoescape=True)) if q else s)
    return (parts[0] if len(parts) == 1 else union_all(*parts)).subquery()


@router.get("/documents", response_model=Page[DocumentListItem], summary="Generation history (resumes and cover letters)")
def list_documents(
    type: Literal["resume", "cover_letter"] | None = None, q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    sub = _docs_query(user.id, type, q)
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    rows = db.execute(select(sub).order_by(sub.c.created_at.desc(), sub.c.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
    items = [DocumentListItem(id=r.id, type=r.type, title=r.title, status=r.status, created_at=r.created_at) for r in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/templates", response_model=list[TemplateOut], summary="Available resume templates")
def list_templates(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(DocumentTemplate).where(DocumentTemplate.is_active.is_(True)).order_by(DocumentTemplate.id)))


@router.get("/dashboard/stats", response_model=DashboardOut, summary="Dashboard statistics")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = lambda model: db.scalar(select(func.count()).select_from(model).where(model.user_id == user.id)) or 0  # noqa: E731
    scores = [(a or {}).get("keyword_score") for a in db.scalars(select(JobAnalysis.match_result).where(JobAnalysis.user_id == user.id))]
    scores = [s for s in scores if isinstance(s, (int, float))]
    sub = _docs_query(user.id, None, None)
    recent = db.execute(select(sub).order_by(sub.c.created_at.desc(), sub.c.id.desc()).limit(5)).all()
    return DashboardOut(
        profile_completeness=completeness(get_or_create_profile(db, user)).percentage,
        counts={"resumes": count(GeneratedResume), "cover_letters": count(GeneratedCoverLetter), "analyses": count(JobAnalysis)},
        average_keyword_score=round(sum(scores) / len(scores), 1) if scores else None,
        recent=[DocumentListItem(id=r.id, type=r.type, title=r.title, status=r.status, created_at=r.created_at) for r in recent],
    )
