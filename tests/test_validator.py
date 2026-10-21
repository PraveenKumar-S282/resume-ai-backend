from datetime import date
from types import SimpleNamespace as NS

from app.ai.validator import build_context, clean_bullets, clean_text, violations


def ctx():
    profile = NS(
        phone="9876543210", summary="Built a portal used by 200 villagers with Python.", headline="", achievements=[],
        skills=[NS(name="Python"), NS(name="MySQL")], projects=[NS(title="Portal", description="React app", tech_stack=["React"], start_date=None, end_date=None)],
        experience=[NS(role="Intern", company="X", bullets=["Wrote Flask APIs"], start_date=date(2025, 6, 1), end_date=date(2025, 8, 1))],
        certifications=[], education=[NS(start_date=date(2023, 8, 1), end_date=date(2027, 5, 1), grade="8.4 CGPA")],
    )
    return build_context(profile)


def test_supported_text_passes():
    assert violations("Built a portal for 200 villagers using Python, React and Flask.", ctx()) == []


def test_invented_number_flagged():
    assert violations("Improved performance by 40%.", ctx()) == ["number '40%'"]


def test_invented_skill_flagged():
    assert violations("Deployed services on Kubernetes.", ctx()) == ["skill 'kubernetes'"]


def test_dates_and_grade_from_profile_are_allowed():
    assert violations("Graduating in 2027 with an 8.4 CGPA.", ctx()) == []


def test_clean_text_drops_only_the_bad_sentence():
    c = ctx()
    out = clean_text("Built a portal with Python. Reduced costs by 35%. Enjoys learning.", c)
    assert out == "Built a portal with Python. Enjoys learning."
    assert len(c.removed) == 1 and "35%" in c.removed[0]


def test_clean_bullets_filters_and_records():
    c = ctx()
    assert clean_bullets(["Wrote Flask APIs", "Scaled Docker clusters to 10 nodes"], c) == ["Wrote Flask APIs"]
    assert c.removed
