from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.llm_client import LLMClient, get_llm
from app.api.deps import get_current_user, get_owned_or_404
from app.core.rate_limit import GENERATION_LIMIT, limiter
from app.db.session import get_db
from app.models import GeneratedCoverLetter, GeneratedResume, JobAnalysis, User
from app.schemas.common import Page
from app.schemas.documents import AnalysisDocuments, AnalysisIn, AnalysisOut, AnalysisSummary, DocRef
from app.services.jd_analyzer import analyze_jd
from app.services.matcher import match_profile
from app.services.profile_service import get_or_create_profile
from app.services.suggestion_service import analysis_suggestions

router = APIRouter(prefix="/analyses", tags=["job analysis"])


def _out(db: Session, a: JobAnalysis) -> AnalysisOut:
    out = AnalysisOut.model_validate(a)
    resumes = db.execute(select(GeneratedResume.id, GeneratedResume.title).where(GeneratedResume.analysis_id == a.id).order_by(GeneratedResume.id.desc()))
    letters = db.execute(select(GeneratedCoverLetter.id, GeneratedCoverLetter.title).where(GeneratedCoverLetter.analysis_id == a.id).order_by(GeneratedCoverLetter.id.desc()))
    out.documents = AnalysisDocuments(
        resumes=[DocRef(id=i, title=t) for i, t in resumes], cover_letters=[DocRef(id=i, title=t) for i, t in letters],
    )
    return out


@router.post("", response_model=AnalysisOut, status_code=201, summary="Analyse a job description against my profile")
@limiter.limit(GENERATION_LIMIT)
def create_analysis(
    request: Request, data: AnalysisIn, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), llm: LLMClient = Depends(get_llm),
):
    profile = get_or_create_profile(db, user)
    extraction, method = analyze_jd(llm, data.jd_text)
    match = match_profile(extraction.required_skills, extraction.preferred_skills, profile)
    suggestions = analysis_suggestions(match["missing_skills"], profile)
    analysis = JobAnalysis(
        user_id=user.id, job_title=extraction.job_title or None, company=extraction.company, jd_text=data.jd_text,
        required_skills=extraction.required_skills, preferred_skills=extraction.preferred_skills,
        experience_requirement=extraction.experience_requirement, keywords=extraction.keywords,
        match_result={**match, "suggestions": [s.model_dump() for s in suggestions], "extraction": method},
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return _out(db, analysis)


@router.get("", response_model=Page[AnalysisSummary], summary="List my analyses")
def list_analyses(
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    total = db.scalar(select(func.count()).select_from(JobAnalysis).where(JobAnalysis.user_id == user.id)) or 0
    rows = db.scalars(
        select(JobAnalysis).where(JobAnalysis.user_id == user.id)
        .order_by(JobAnalysis.created_at.desc(), JobAnalysis.id.desc()).limit(page_size).offset((page - 1) * page_size)
    )
    items = [AnalysisSummary(id=a.id, job_title=a.job_title, company=a.company, keyword_score=(a.match_result or {}).get("keyword_score"), created_at=a.created_at) for a in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{analysis_id}", response_model=AnalysisOut, summary="Get one analysis")
def get_analysis(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _out(db, get_owned_or_404(db, JobAnalysis, analysis_id, user.id, "Analysis"))


@router.delete("/{analysis_id}", status_code=204, summary="Delete an analysis (documents are kept)")
def delete_analysis(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(get_owned_or_404(db, JobAnalysis, analysis_id, user.id, "Analysis"))
    db.commit()
    return Response(status_code=204)
