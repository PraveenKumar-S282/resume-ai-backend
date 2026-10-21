from datetime import date

from app.ai import prompts
from app.ai.llm_client import LLMClient
from app.ai.schemas import ResumeDraft
from app.ai.validator import build_context, clean_bullets, clean_text, violations
from app.models import CandidateProfile, JobAnalysis, User
from app.schemas.documents import (
    CertificationItem, EducationItem, ExperienceItem, Header, Link, Preferences, ProjectItem, ResumeContent, SkillGroup,
)
from app.services.matcher import canonical, text_mentions
from app.services.profile_service import candidate_dict, month_year

CATEGORY_ORDER = ["language", "framework", "database", "tool", "soft", "other"]
CATEGORY_LABEL = {
    "language": "Languages", "framework": "Frameworks and Libraries", "database": "Databases",
    "tool": "Tools and Platforms", "soft": "Soft Skills", "other": "Other",
}


def analysis_payload(a: JobAnalysis) -> dict:
    return {
        "job_title": a.job_title, "company": a.company, "required_skills": a.required_skills,
        "preferred_skills": a.preferred_skills, "keywords": a.keywords, "experience_requirement": a.experience_requirement,
    }


def _draft_text(d: ResumeDraft) -> list[str]:
    return [d.summary, *[b for e in d.experience for b in e.bullets], *[b for p in d.projects for b in p.bullets]]


def _build_skills(profile: CandidateProfile, analysis: JobAnalysis) -> list[SkillGroup]:
    jd_terms = [*analysis.required_skills, *analysis.preferred_skills]
    jd_keys = {canonical(s) for s in jd_terms}
    groups: dict[str, list[str]] = {}
    for s in profile.skills:
        groups.setdefault(s.category if s.category in CATEGORY_LABEL else "other", []).append(s.name)
    out = []
    for cat in CATEGORY_ORDER:
        names = groups.get(cat)
        if names:
            names.sort(key=lambda n: (canonical(n) not in jd_keys, n.lower()))  # job-relevant first
            out.append(SkillGroup(category=CATEGORY_LABEL[cat], items=names))
    return out


def _education(profile: CandidateProfile) -> list[EducationItem]:
    items = sorted(profile.education, key=lambda e: (e.end_date or date.min, e.start_date or date.min), reverse=True)
    out = []
    for e in items:
        years = " to ".join(str(d.year) for d in (e.start_date, e.end_date) if d)
        degree = e.degree + (f", {e.field}" if e.field else "")
        out.append(EducationItem(institution=e.institution, degree=degree, dates=years or None, grade=e.grade))
    return out


def generate_resume_content(
    llm: LLMClient, profile: CandidateProfile, user: User, analysis: JobAnalysis, prefs: Preferences,
) -> tuple[ResumeContent, list[str]]:
    """Returns (content, removed). `removed` lists AI text dropped because the profile did not support it."""
    candidate = candidate_dict(profile, user)
    payload = analysis_payload(analysis)
    p = prefs.model_dump()
    ctx = build_context(profile)

    draft = llm.generate_json(*prompts.resume(candidate, payload, p), ResumeDraft)
    problems = sorted({v for t in _draft_text(draft) for v in violations(t, ctx)})
    if problems:  # one corrective retry
        draft = llm.generate_json(*prompts.resume(candidate, payload, p, feedback=", ".join(problems)), ResumeDraft)

    one_page = prefs.length == "one_page"
    max_bullets = 3 if one_page else 5
    max_projects = 3 if one_page else 6
    proj_bullets = 2 if one_page else 4

    drafts_exp = {e.id: e.bullets for e in draft.experience}
    experience = []
    for e in sorted(profile.experience, key=lambda x: (x.is_current, x.end_date or date.min, x.start_date or date.min), reverse=True):
        source = e.bullets or []
        bullets = clean_bullets(drafts_exp.get(e.id, []), ctx) if source else []
        if source and not bullets:
            bullets = list(source)  # fall back to the candidate's own words
        experience.append(ExperienceItem(
            role=e.role, company=e.company, location=e.location, start=month_year(e.start_date),
            end="Present" if e.is_current else month_year(e.end_date), bullets=bullets[:max_bullets],
        ))

    by_id = {pr.id: pr for pr in profile.projects}
    order = [d.id for d in draft.projects if d.id in by_id] or [pr.id for pr in profile.projects]
    seen, ordered = set(), []
    for i in order:
        if i not in seen:
            seen.add(i)
            ordered.append(i)
    drafts_proj = {d.id: d.bullets for d in draft.projects}
    projects = []
    for i in ordered[:max_projects]:
        pr = by_id[i]
        bullets = clean_bullets(drafts_proj.get(i, []), ctx) if pr.description else []
        if pr.description and not bullets:
            bullets = [pr.description.strip()[:300]]
        projects.append(ProjectItem(title=pr.title, tech=pr.tech_stack or [], url=pr.url, bullets=bullets[:proj_bullets]))

    summary = clean_text(draft.summary, ctx) or (profile.summary or "")

    links = [Link(label=lbl, url=u) for lbl, u in
             (("LinkedIn", profile.linkedin_url), ("GitHub", profile.github_url), ("Portfolio", profile.portfolio_url)) if u]
    content = ResumeContent(
        header=Header(name=user.full_name, headline=profile.headline, email=user.email, phone=profile.phone, location=profile.location, links=links),
        summary=summary,
        skills=_build_skills(profile, analysis),
        experience=experience,
        projects=projects,
        education=_education(profile),
        certifications=[CertificationItem(name=c.name, issuer=c.issuer, date=month_year(c.issue_date)) for c in profile.certifications],
    )
    return content, ctx.removed


def resume_title(analysis: JobAnalysis) -> str:
    t = analysis.job_title or "Resume"
    return f"{t} at {analysis.company}" if analysis.company else t
