from app.ai import prompts
from app.ai.llm_client import LLMClient, LLMError
from app.ai.schemas import CoverLetterDraft
from app.ai.validator import build_context, clean_text, violations
from app.models import CandidateProfile, JobAnalysis, User
from app.schemas.documents import Preferences, ResumeContent
from app.services.profile_service import candidate_dict
from app.services.resume_service import analysis_payload


def _highlights(resume: ResumeContent | None) -> dict | None:
    if not resume:
        return None
    return {
        "summary": resume.summary,
        "projects": [p.title for p in resume.projects],
        "skills": [s for g in resume.skills for s in g.items][:15],
    }


def generate_cover_letter_text(
    llm: LLMClient, profile: CandidateProfile, user: User, analysis: JobAnalysis, prefs: Preferences, resume: ResumeContent | None,
) -> tuple[str, list[str]]:
    candidate = candidate_dict(profile, user)
    payload = analysis_payload(analysis)
    p = prefs.model_dump()
    ctx = build_context(profile)
    hl = _highlights(resume)

    draft = llm.generate_json(*prompts.cover_letter(candidate, payload, p, hl), CoverLetterDraft)
    problems = sorted({v for para in draft.paragraphs for v in violations(para, ctx)})
    if problems:
        draft = llm.generate_json(*prompts.cover_letter(candidate, payload, p, hl, feedback=", ".join(problems)), CoverLetterDraft)

    paragraphs = [clean_text(para, ctx) for para in draft.paragraphs]
    paragraphs = [para for para in paragraphs if para]
    if not paragraphs:
        raise LLMError("The AI could not write a letter supported by your profile. Add more detail to your profile and try again.")

    greeting = "Dear Hiring Manager,"
    text = "\n\n".join([greeting, *paragraphs, f"Sincerely,\n{user.full_name}"])
    return text, ctx.removed


def letter_title(analysis: JobAnalysis) -> str:
    t = analysis.job_title or "Cover letter"
    return f"Cover letter: {t}" + (f" at {analysis.company}" if analysis.company else "")
