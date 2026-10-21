"""Resume scoring. All scores are deterministic estimates of keyword overlap and completeness."""
from app.schemas.documents import ResumeContent
from app.services.matcher import text_mentions


def resume_text(c: ResumeContent) -> str:
    parts = [c.header.headline or "", c.summary]
    for g in c.skills:
        parts += [g.category, *g.items]
    for e in c.experience:
        parts += [e.role, e.company, *e.bullets]
    for p in c.projects:
        parts += [p.title, *p.tech, *p.bullets]
    for ed in c.education:
        parts += [ed.degree, ed.institution]
    for cert in c.certifications:
        parts.append(cert.name)
    return "\n".join(parts)


def _units(c: ResumeContent) -> list[str]:
    units = [c.summary] if c.summary else []
    for e in c.experience:
        units += e.bullets
    for p in c.projects:
        units += p.bullets
    return [u for u in units if u.strip()]


def score_resume(c: ResumeContent, required: list[str], preferred: list[str], keywords: list[str]) -> dict:
    text = resume_text(c)

    total = 2 * len(required) + len(preferred)
    got = sum(2 for s in required if text_mentions(text, s)) + sum(1 for s in preferred if text_mentions(text, s))
    all_terms = list(dict.fromkeys([*required, *preferred, *keywords]))
    matched = [t for t in all_terms if text_mentions(text, t)]
    missing = [t for t in all_terms if t not in matched]
    if total == 0 and all_terms:
        keyword = 100 * len(matched) / len(all_terms)
    else:
        keyword = 100 * got / total if total else 0.0

    checks = [
        bool(c.summary.strip()),
        bool(c.skills),
        bool(c.experience or c.projects),
        bool(c.education),
        bool(c.header.email and (c.header.phone or c.header.location)),
    ]
    completeness = 100 * sum(checks) / len(checks)

    units = _units(c)
    relevant = sum(1 for u in units if any(text_mentions(u, t) for t in all_terms))
    relevance = 100 * relevant / len(units) if units else 0.0

    return {
        "scores": {"keyword": round(keyword, 1), "completeness": round(completeness, 1), "relevance": round(relevance, 1)},
        "matched_keywords": matched,
        "missing_keywords": missing,
    }
