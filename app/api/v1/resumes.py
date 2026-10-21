from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm_client import LLMClient, LLMError, get_llm
from app.api.deps import get_current_user, get_owned_or_404
from app.api.v1._common import file_response, get_template, require_analysis
from app.core.errors import AppError
from app.core.rate_limit import GENERATION_LIMIT, limiter
from app.db.session import get_db
from app.documents.docx_builder import build_resume_docx
from app.documents.pdf_builder import build_resume_pdf
from app.documents.templates import config_for
from app.models import GeneratedResume, JobAnalysis, User
from app.schemas.documents import (
    DocumentListItem, GenerateResumeIn, ImproveOut, Preferences, ResumeContent, ResumeOut, ResumeUpdate,
)
from app.services.profile_service import get_or_create_profile, missing_for_generation
from app.services.resume_service import generate_resume_content, resume_title
from app.services.scorer import score_resume
from app.services.suggestion_service import resume_suggestions

router = APIRouter(tags=["resumes"])


def _generate(db: Session, llm: LLMClient, user: User, analysis: JobAnalysis, prefs: Preferences):
    profile = get_or_create_profile(db, user)
    missing = missing_for_generation(profile)
    if missing:
        raise AppError(422, "MISSING_PROFILE_DATA", "Your profile needs more information before a resume can be written.", missing)
    try:
        content, removed = generate_resume_content(llm, profile, user, analysis, prefs)
    except LLMError as exc:
        raise AppError(502, "AI_UNAVAILABLE", str(exc)) from exc
    sc = score_resume(content, analysis.required_skills, analysis.preferred_skills, analysis.keywords)
    scores = {**sc["scores"], "verification": {"removed": removed}}
    return content, scores


@router.post("/analyses/{analysis_id}/resumes", response_model=ResumeOut, status_code=201, summary="Generate a tailored resume")
@limiter.limit(GENERATION_LIMIT)
def create_resume(
    request: Request, analysis_id: int, body: GenerateResumeIn, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), llm: LLMClient = Depends(get_llm),
):
    analysis = get_owned_or_404(db, JobAnalysis, analysis_id, user.id, "Analysis")
    template = get_template(db, body.template_key)
    content, scores = _generate(db, llm, user, analysis, body.preferences)
    resume = GeneratedResume(
        user_id=user.id, analysis_id=analysis.id, template_id=template.id, title=resume_title(analysis),
        content=content.model_dump(), preferences=body.preferences.model_dump(), scores=scores, version=1, status="draft",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resumes", response_model=list[DocumentListItem], summary="List my resumes")
def list_resumes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(GeneratedResume).where(GeneratedResume.user_id == user.id).order_by(GeneratedResume.created_at.desc(), GeneratedResume.id.desc()))
    return [DocumentListItem(id=r.id, type="resume", title=r.title, status=r.status, created_at=r.created_at) for r in rows]


@router.get("/resumes/{resume_id}", response_model=ResumeOut, summary="Get a resume")
def get_resume(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_owned_or_404(db, GeneratedResume, resume_id, user.id, "Resume")


@router.patch("/resumes/{resume_id}", response_model=ResumeOut, summary="Edit or save a resume")
def update_resume(resume_id: int, data: ResumeUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = get_owned_or_404(db, GeneratedResume, resume_id, user.id, "Resume")
    if data.title is not None:
        resume.title = data.title.strip()
    if data.template_key is not None:
        resume.template_id = get_template(db, data.template_key).id
    if data.content is not None:
        resume.content = data.content.model_dump()
    if data.status is not None:
        resume.status = data.status
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/regenerate", response_model=ResumeOut, summary="Regenerate (new version)")
@limiter.limit(GENERATION_LIMIT)
def regenerate_resume(
    request: Request, resume_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), llm: LLMClient = Depends(get_llm),
):
    resume = get_owned_or_404(db, GeneratedResume, resume_id, user.id, "Resume")
    analysis = require_analysis(db, resume.analysis_id)
    content, scores = _generate(db, llm, user, analysis, Preferences(**(resume.preferences or {})))
    resume.content = content.model_dump()
    resume.scores = scores
    resume.version += 1
    resume.status = "draft"
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/improve", response_model=ImproveOut, summary="Keyword analysis and improvement suggestions")
def improve_resume(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = get_owned_or_404(db, GeneratedResume, resume_id, user.id, "Resume")
    analysis = require_analysis(db, resume.analysis_id)
    content = ResumeContent(**resume.content)
    sc = score_resume(content, analysis.required_skills, analysis.preferred_skills, analysis.keywords)
    profile = get_or_create_profile(db, user)
    suggestions = resume_suggestions(content, sc["scores"], sc["missing_keywords"], profile)
    resume.scores = {**(resume.scores or {}), **sc["scores"]}
    db.commit()
    return ImproveOut(scores=sc["scores"], matched_keywords=sc["matched_keywords"], missing_keywords=sc["missing_keywords"], suggestions=suggestions)


@router.delete("/resumes/{resume_id}", status_code=204, summary="Delete a resume")
def delete_resume(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(get_owned_or_404(db, GeneratedResume, resume_id, user.id, "Resume"))
    db.commit()
    return Response(status_code=204)


@router.get("/resumes/{resume_id}/download", summary="Download as PDF or DOCX")
def download_resume(
    resume_id: int, format: Literal["pdf", "docx"] = Query("pdf"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    resume = get_owned_or_404(db, GeneratedResume, resume_id, user.id, "Resume")
    cfg = config_for(resume.template_key, resume.template.config if resume.template else None)
    content = ResumeContent(**resume.content)
    data = build_resume_pdf(content, cfg) if format == "pdf" else build_resume_docx(content, cfg)
    return file_response(data, format, resume.title)
