from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm_client import LLMClient, LLMError, get_llm
from app.api.deps import get_current_user, get_owned_or_404
from app.api.v1._common import file_response, require_analysis
from app.core.errors import AppError
from app.core.rate_limit import GENERATION_LIMIT, limiter
from app.db.session import get_db
from app.documents.docx_builder import build_cover_letter_docx
from app.documents.pdf_builder import build_cover_letter_pdf
from app.documents.templates import config_for
from app.models import GeneratedCoverLetter, GeneratedResume, JobAnalysis, User
from app.schemas.documents import CoverLetterOut, CoverLetterUpdate, DocumentListItem, GenerateCoverLetterIn, Preferences, ResumeContent
from app.services.cover_letter_service import generate_cover_letter_text, letter_title
from app.services.profile_service import get_or_create_profile, missing_for_generation

router = APIRouter(tags=["cover letters"])


def _linked_resume(db: Session, user: User, resume_id: int | None) -> GeneratedResume | None:
    return get_owned_or_404(db, GeneratedResume, resume_id, user.id, "Resume") if resume_id else None


def _write(db: Session, llm: LLMClient, user: User, analysis: JobAnalysis, prefs: Preferences, resume: GeneratedResume | None) -> str:
    profile = get_or_create_profile(db, user)
    missing = missing_for_generation(profile)
    if missing:
        raise AppError(422, "MISSING_PROFILE_DATA", "Your profile needs more information before a cover letter can be written.", missing)
    try:
        text, _removed = generate_cover_letter_text(llm, profile, user, analysis, prefs, ResumeContent(**resume.content) if resume else None)
    except LLMError as exc:
        raise AppError(502, "AI_UNAVAILABLE", str(exc)) from exc
    return text


@router.post("/analyses/{analysis_id}/cover-letters", response_model=CoverLetterOut, status_code=201, summary="Generate a matching cover letter")
@limiter.limit(GENERATION_LIMIT)
def create_cover_letter(
    request: Request, analysis_id: int, body: GenerateCoverLetterIn, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), llm: LLMClient = Depends(get_llm),
):
    analysis = get_owned_or_404(db, JobAnalysis, analysis_id, user.id, "Analysis")
    resume = _linked_resume(db, user, body.resume_id)
    text = _write(db, llm, user, analysis, body.preferences, resume)
    letter = GeneratedCoverLetter(
        user_id=user.id, analysis_id=analysis.id, resume_id=resume.id if resume else None, title=letter_title(analysis),
        content=text, preferences=body.preferences.model_dump(), version=1, status="draft",
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    return letter


@router.get("/cover-letters", response_model=list[DocumentListItem], summary="List my cover letters")
def list_cover_letters(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(GeneratedCoverLetter).where(GeneratedCoverLetter.user_id == user.id).order_by(GeneratedCoverLetter.created_at.desc(), GeneratedCoverLetter.id.desc()))
    return [DocumentListItem(id=r.id, type="cover_letter", title=r.title, status=r.status, created_at=r.created_at) for r in rows]


@router.get("/cover-letters/{letter_id}", response_model=CoverLetterOut, summary="Get a cover letter")
def get_cover_letter(letter_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_owned_or_404(db, GeneratedCoverLetter, letter_id, user.id, "Cover letter")


@router.patch("/cover-letters/{letter_id}", response_model=CoverLetterOut, summary="Edit or save a cover letter")
def update_cover_letter(letter_id: int, data: CoverLetterUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    letter = get_owned_or_404(db, GeneratedCoverLetter, letter_id, user.id, "Cover letter")
    if data.title is not None:
        letter.title = data.title.strip()
    if data.content is not None:
        letter.content = data.content
    if data.status is not None:
        letter.status = data.status
    db.commit()
    db.refresh(letter)
    return letter


@router.post("/cover-letters/{letter_id}/regenerate", response_model=CoverLetterOut, summary="Regenerate (new version)")
@limiter.limit(GENERATION_LIMIT)
def regenerate_cover_letter(
    request: Request, letter_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), llm: LLMClient = Depends(get_llm),
):
    letter = get_owned_or_404(db, GeneratedCoverLetter, letter_id, user.id, "Cover letter")
    analysis = require_analysis(db, letter.analysis_id)
    resume = db.get(GeneratedResume, letter.resume_id) if letter.resume_id else None
    letter.content = _write(db, llm, user, analysis, Preferences(**(letter.preferences or {})), resume)
    letter.version += 1
    letter.status = "draft"
    db.commit()
    db.refresh(letter)
    return letter


@router.delete("/cover-letters/{letter_id}", status_code=204, summary="Delete a cover letter")
def delete_cover_letter(letter_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(get_owned_or_404(db, GeneratedCoverLetter, letter_id, user.id, "Cover letter"))
    db.commit()
    return Response(status_code=204)


@router.get("/cover-letters/{letter_id}/download", summary="Download as PDF or DOCX")
def download_cover_letter(
    letter_id: int, format: Literal["pdf", "docx"] = Query("pdf"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    letter = get_owned_or_404(db, GeneratedCoverLetter, letter_id, user.id, "Cover letter")
    resume = db.get(GeneratedResume, letter.resume_id) if letter.resume_id else None
    cfg = config_for(resume.template_key if resume else "classic", resume.template.config if resume and resume.template else None)
    data = build_cover_letter_pdf(letter.content, cfg) if format == "pdf" else build_cover_letter_docx(letter.content, cfg)
    return file_response(data, format, letter.title)
