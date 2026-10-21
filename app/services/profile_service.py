from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CandidateProfile, User
from app.schemas.profile import Completeness


def get_or_create_profile(db: Session, user: User) -> CandidateProfile:
    profile = db.scalar(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .options(
            selectinload(CandidateProfile.education), selectinload(CandidateProfile.experience),
            selectinload(CandidateProfile.skills), selectinload(CandidateProfile.projects),
            selectinload(CandidateProfile.certifications),
        )
    )
    if profile is None:
        profile = CandidateProfile(user_id=user.id, achievements=[])
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def completeness(profile: CandidateProfile) -> Completeness:
    checks = {
        "headline": bool(profile.headline),
        "summary": bool(profile.summary),
        "phone number": bool(profile.phone),
        "location": bool(profile.location),
        "education": len(profile.education) > 0,
        "skills": len(profile.skills) > 0,
        "work experience or projects": len(profile.experience) + len(profile.projects) > 0,
    }
    missing = [k for k, ok in checks.items() if not ok]
    return Completeness(percentage=round(100 * (len(checks) - len(missing)) / len(checks)), missing=missing)


def missing_for_generation(profile: CandidateProfile) -> list[dict]:
    """Hard requirements before a document can be written without inventing anything."""
    out = []
    if not profile.education:
        out.append({"field": "education", "issue": "Add at least one education entry."})
    if not profile.skills:
        out.append({"field": "skills", "issue": "Add the skills you actually have."})
    if not profile.experience and not profile.projects:
        out.append({"field": "experience", "issue": "Add at least one work experience or project."})
    return out


def month_year(d: date | None) -> str | None:
    return d.strftime("%b %Y") if d else None


def candidate_dict(profile: CandidateProfile, user: User) -> dict:
    """Everything the LLM is allowed to use, with ids so output can be mapped back to real rows."""
    return {
        "name": user.full_name,
        "headline": profile.headline,
        "summary": profile.summary,
        "achievements": profile.achievements or [],
        "education": [
            {"institution": e.institution, "degree": e.degree, "field": e.field, "grade": e.grade,
             "start": str(e.start_date or ""), "end": str(e.end_date or "")}
            for e in profile.education
        ],
        "experience": [
            {"id": e.id, "role": e.role, "company": e.company, "start": month_year(e.start_date),
             "end": "Present" if e.is_current else month_year(e.end_date), "bullets": e.bullets or []}
            for e in profile.experience
        ],
        "projects": [
            {"id": p.id, "title": p.title, "description": p.description, "tech_stack": p.tech_stack or []}
            for p in profile.projects
        ],
        "skills": [{"name": s.name, "category": s.category} for s in profile.skills],
        "certifications": [{"name": c.name, "issuer": c.issuer} for c in profile.certifications],
    }
