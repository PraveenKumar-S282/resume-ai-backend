"""Rule-based improvement suggestions. Never recommends adding anything the candidate does not have."""
import re

from app.models import CandidateProfile
from app.schemas.documents import ResumeContent, Suggestion
from app.services.matcher import has_skill, profile_skill_set, profile_text
from app.services.scorer import resume_text

_ORDER = {"high": 0, "medium": 1, "low": 2}


def skill_gap_suggestions(missing_required: list[str], profile: CandidateProfile, limit: int = 5) -> list[Suggestion]:
    skills, text = profile_skill_set(profile), profile_text(profile)
    out = []
    for s in missing_required[:limit]:
        if has_skill(s, skills, text):
            continue
        out.append(Suggestion(
            priority="medium",
            message=f"The job asks for {s}, which is not in your profile. Add it only if you have real experience with it; otherwise do not claim it.",
        ))
    return out


def analysis_suggestions(missing_required: list[str], profile: CandidateProfile) -> list[Suggestion]:
    out = skill_gap_suggestions(missing_required, profile)
    if not profile.summary:
        out.append(Suggestion(priority="medium", message="Add a short professional summary to your profile so it can be tailored to this job."))
    if not (profile.experience or profile.projects):
        out.append(Suggestion(priority="high", message="Add at least one work experience or project; the resume needs real material to draw on."))
    return out


def resume_suggestions(content: ResumeContent, scores: dict, missing_keywords: list[str], profile: CandidateProfile | None) -> list[Suggestion]:
    out: list[Suggestion] = []
    text = resume_text(content)
    skills = profile_skill_set(profile) if profile else set()
    ptext = profile_text(profile) if profile else ""

    if scores["keyword"] < 50:
        out.append(Suggestion(priority="high", message="Keyword overlap with the job is low. Check the missing keywords below and add the ones you genuinely have to your profile."))

    shown = 0
    for kw in missing_keywords:
        if shown >= 5:
            break
        if profile and has_skill(kw, skills, ptext):
            out.append(Suggestion(priority="high", message=f"Your profile mentions {kw}, but this resume does not. Consider regenerating with that area emphasised or adding it to a bullet."))
        else:
            out.append(Suggestion(priority="medium", message=f"'{kw}' appears in the job but not in your profile. Include it only if it truthfully applies to you."))
        shown += 1

    if not content.summary.strip():
        out.append(Suggestion(priority="high", message="The resume has no summary. A two or three sentence summary helps a reader see the fit quickly."))
    for e in content.experience:
        if not e.bullets:
            out.append(Suggestion(priority="medium", message=f"Add detail about what you did as {e.role or 'your role'} at {e.company or 'this company'}."))
    for p in content.projects:
        if not p.bullets:
            out.append(Suggestion(priority="medium", message=f"Describe what you built in '{p.title}' and which technologies you used."))
    if not re.search(r"\d", " ".join(b for e in content.experience for b in e.bullets) + " ".join(b for p in content.projects for b in p.bullets)):
        out.append(Suggestion(priority="low", message="If you have measurable results (users, speed, size, time saved), add them. Only include numbers that are true."))
    if not content.header.links:
        out.append(Suggestion(priority="low", message="Add a GitHub, LinkedIn or portfolio link to your profile so employers can see your work."))
    words = len(text.split())
    if words > 650:
        out.append(Suggestion(priority="low", message=f"The resume is about {words} words. Shorter is easier to scan; consider the one-page length option."))
    if not out:
        out.append(Suggestion(priority="low", message="This resume covers what the job asks for. Proofread it once more before sending."))
    return sorted(out, key=lambda s: _ORDER[s.priority])
