"""Deterministic skill normalisation and matching (no LLM, fully reproducible)."""
import json
import re
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz

_DATA = Path(__file__).resolve().parent.parent / "data" / "skill_synonyms.json"
FUZZY_THRESHOLD = 92
# Aliases that are also everyday words/abbreviations: fine as a skill NAME, unsafe to search for inside free text.
AMBIGUOUS_ALIASES = {"go", "express", "ts", "py", "ml"}


@lru_cache
def _lexicon() -> tuple[dict[str, str], dict[str, list[str]]]:
    raw: dict[str, list[str]] = json.loads(_DATA.read_text(encoding="utf-8"))
    alias_to_canon: dict[str, str] = {}
    terms: dict[str, list[str]] = {}
    for canon, aliases in raw.items():
        alias_to_canon[_basic(canon)] = canon
        terms[canon] = [canon, *[a for a in aliases if a not in AMBIGUOUS_ALIASES]]
        for a in aliases:
            alias_to_canon[_basic(a)] = canon
    return alias_to_canon, terms


def _basic(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s+#./-]", " ", s)
    return re.sub(r"\s+", " ", s).strip(" .-/")


def canonical(skill: str) -> str:
    """Map a skill name to its canonical form (e.g. 'JS' -> 'javascript')."""
    b = _basic(skill)
    alias_to_canon, _ = _lexicon()
    return alias_to_canon.get(b, b)


def lexicon_terms() -> dict[str, list[str]]:
    return _lexicon()[1]


def _contains(text: str, term: str) -> bool:
    pattern = r"(?<![a-z0-9+#.])" + re.escape(term.lower()) + r"(?![a-z0-9+#])"
    return re.search(pattern, text) is not None


def text_mentions(text: str, skill: str) -> bool:
    """True if the text mentions the skill or any known alias, on word boundaries."""
    canon = canonical(skill)
    _, terms = _lexicon()
    candidates = terms.get(canon, [canon])
    low = text.lower()
    return any(_contains(low, t) for t in candidates)


def find_lexicon_skills(text: str) -> list[str]:
    """All lexicon skills mentioned in the text, in lexicon order."""
    return [canon for canon in lexicon_terms() if text_mentions(text, canon)]


def _same(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 4:
        return False
    return fuzz.ratio(a, b) >= FUZZY_THRESHOLD


def profile_skill_set(profile) -> set[str]:
    """Canonical skills the candidate has listed (skills table plus project tech stacks)."""
    out = {canonical(s.name) for s in profile.skills}
    for p in profile.projects:
        out.update(canonical(t) for t in (p.tech_stack or []))
    return out


def profile_text(profile) -> str:
    parts = [profile.summary or "", profile.headline or ""]
    for e in profile.experience:
        parts += [e.role or "", e.company or "", *(e.bullets or [])]
    for p in profile.projects:
        parts += [p.title or "", p.description or ""]
    for c in profile.certifications:
        parts.append(c.name or "")
    parts += list(profile.achievements or [])
    return "\n".join(parts)


def has_skill(skill: str, skill_set: set[str], text: str) -> bool:
    c = canonical(skill)
    if any(_same(c, s) for s in skill_set):
        return True
    return text_mentions(text, skill)


def match_profile(required: list[str], preferred: list[str], profile) -> dict:
    skill_set = profile_skill_set(profile)
    text = profile_text(profile)

    matched_req = [s for s in required if has_skill(s, skill_set, text)]
    missing_req = [s for s in required if s not in matched_req]
    matched_pref = [s for s in preferred if has_skill(s, skill_set, text)]
    missing_pref = [s for s in preferred if s not in matched_pref]

    total = 2 * len(required) + len(preferred)
    got = 2 * len(matched_req) + len(matched_pref)
    score = round(100 * got / total, 1) if total else 0.0
    return {
        "matched_skills": matched_req + matched_pref,
        "missing_skills": missing_req,
        "missing_preferred": missing_pref,
        "keyword_score": score,
    }
