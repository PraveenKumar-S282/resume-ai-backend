"""Anti-fabrication checks. The LLM may rephrase profile facts but not add new ones.

A text is flagged if it mentions
  - a number/percentage that does not appear in the candidate's own text, or
  - a known skill (lexicon) that the candidate never listed or described.
"""
import re
from dataclasses import dataclass, field

from app.services.matcher import find_lexicon_skills, has_skill, profile_skill_set, profile_text

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
_SENT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Context:
    skills: set[str]
    text: str
    numbers: set[str]
    removed: list[str] = field(default_factory=list)


def build_context(profile) -> Context:
    text = profile_text(profile)
    # Dates, years, grades and phone digits the candidate typed are also "their" numbers.
    extra = " ".join(
        str(x) for x in [profile.phone or ""]
        + [f"{e.start_date} {e.end_date} {e.grade or ''}" for e in profile.education]
        + [f"{e.start_date} {e.end_date}" for e in profile.experience]
        + [f"{p.start_date} {p.end_date}" for p in profile.projects]
        + [f"{c.issue_date}" for c in profile.certifications]
    )
    nums = {n.rstrip("%").replace(",", "") for n in _NUM.findall(text + " " + extra)}
    for y in re.findall(r"\d{4}", extra):
        nums.add(y)
    return Context(skills=profile_skill_set(profile), text=text, numbers=nums)


def violations(text: str, ctx: Context) -> list[str]:
    found: list[str] = []
    for n in _NUM.findall(text):
        if n.rstrip("%").replace(",", "") not in ctx.numbers:
            found.append(f"number '{n}'")
    for skill in find_lexicon_skills(text):
        if not has_skill(skill, ctx.skills, ctx.text):
            found.append(f"skill '{skill}'")
    return found


def clean_text(text: str, ctx: Context) -> str:
    """Drop sentences that contain unsupported facts; record what was removed."""
    kept = []
    for sentence in _SENT.split(text.strip()):
        v = violations(sentence, ctx)
        if v:
            ctx.removed.append(f"{sentence[:80]} ({', '.join(v)})")
        elif sentence.strip():
            kept.append(sentence.strip())
    return " ".join(kept)


def clean_bullets(bullets: list[str], ctx: Context) -> list[str]:
    out = []
    for b in bullets:
        b = b.strip()
        if not b:
            continue
        v = violations(b, ctx)
        if v:
            ctx.removed.append(f"{b[:80]} ({', '.join(v)})")
        else:
            out.append(b)
    return out
