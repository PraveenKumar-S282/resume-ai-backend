from types import SimpleNamespace as NS

from app.services.matcher import canonical, find_lexicon_skills, match_profile, text_mentions


def profile(skills=(), tech=(), text=""):
    return NS(
        skills=[NS(name=s) for s in skills], projects=[NS(title="", description="", tech_stack=list(tech))],
        summary=text, headline="", experience=[], certifications=[], achievements=[],
    )


def test_synonyms_normalise():
    assert canonical("JS") == "javascript"
    assert canonical("ReactJS") == "react"
    assert canonical("Node") == "node.js"
    assert canonical("Postgres") == "postgresql"
    assert canonical("RESTful APIs") == "rest apis"
    assert canonical("Go") == "golang"


def test_plural_and_typo_fuzzy_match():
    r = match_profile(["REST API"], [], profile(skills=["REST APIs"]))
    assert r["matched_skills"] == ["REST API"]


def test_skill_found_in_project_tech_stack():
    r = match_profile(["Flask"], [], profile(tech=["Flask"]))
    assert r["missing_skills"] == []


def test_skill_found_in_free_text_with_word_boundaries():
    assert match_profile(["Docker"], [], profile(text="Deployed apps using Docker on Render"))["missing_skills"] == []
    # 'Java' must not match inside 'JavaScript'
    r = match_profile(["Java"], [], profile(skills=["JavaScript"]))
    assert r["missing_skills"] == ["Java"]


def test_missing_skills_and_weighted_score():
    r = match_profile(["Python", "Docker"], ["AWS"], profile(skills=["Python"]))
    assert r["matched_skills"] == ["Python"] and r["missing_skills"] == ["Docker"] and r["missing_preferred"] == ["AWS"]
    assert r["keyword_score"] == 40.0  # (2*1) / (2*2 + 1)


def test_empty_requirements_score_zero():
    assert match_profile([], [], profile())["keyword_score"] == 0.0


def test_lexicon_scan_ignores_ambiguous_words():
    found = find_lexicon_skills("We express our thanks. Ready to go! Experience with Python and CI/CD.")
    assert "python" in found and "ci/cd" in found
    assert "golang" not in found and "express.js" not in found


def test_text_mentions_aliases():
    assert text_mentions("Built apps in ReactJS", "React")
