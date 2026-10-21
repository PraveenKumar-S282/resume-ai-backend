import logging

from app.ai import prompts
from app.ai.llm_client import LLMClient, LLMError
from app.ai.schemas import JDExtraction
from app.services.matcher import canonical, find_lexicon_skills

log = logging.getLogger("app.analysis")


def _dedupe(items: list[str], limit: int, exclude: set[str] | None = None) -> list[str]:
    seen = set(exclude or set())
    out = []
    for s in items:
        s = s.strip()
        key = canonical(s)
        if s and key not in seen:
            seen.add(key)
            out.append(s)
        if len(out) >= limit:
            break
    return out


def analyze_jd(llm: LLMClient, jd_text: str) -> tuple[JDExtraction, str]:
    """Returns (extraction, method). Falls back to the keyword lexicon if the LLM is unavailable."""
    lexicon_skills = find_lexicon_skills(jd_text)
    try:
        raw = llm.generate_json(*prompts.jd_extraction(jd_text), JDExtraction)
        required = _dedupe(raw.required_skills, 25)
        req_keys = {canonical(s) for s in required}
        preferred = _dedupe(raw.preferred_skills, 25, exclude=req_keys)
        used = req_keys | {canonical(s) for s in preferred}
        keywords = _dedupe([*raw.keywords, *[s for s in lexicon_skills if canonical(s) not in used]], 30, exclude=used)
        return JDExtraction(
            job_title=(raw.job_title or "").strip()[:200], company=(raw.company or None),
            required_skills=required, preferred_skills=preferred,
            experience_requirement=raw.experience_requirement, keywords=keywords,
        ), "llm"
    except LLMError as exc:
        log.warning("LLM extraction unavailable, using lexicon fallback: %s", exc)
        first_line = next((ln.strip() for ln in jd_text.splitlines() if ln.strip()), "")
        return JDExtraction(
            job_title=first_line[:100], required_skills=_dedupe(lexicon_skills, 25), preferred_skills=[], keywords=[],
        ), "lexicon"
