from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

SkillCategory = Literal["language", "framework", "tool", "database", "soft", "other"]
Proficiency = Literal["beginner", "intermediate", "advanced"]


def _clean_list(v: list[str] | None) -> list[str]:
    return [s.strip() for s in (v or []) if s and s.strip()]


# ---------- core profile ----------
class ProfileIn(BaseModel):
    headline: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    location: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=1500)
    linkedin_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)
    achievements: list[str] = Field(default_factory=list, max_length=30)

    _a = field_validator("achievements")(_clean_list)


class ProfileOut(ORMModel, ProfileIn):
    id: int


class Completeness(BaseModel):
    percentage: int
    missing: list[str]


# ---------- sections ----------
class EducationIn(BaseModel):
    institution: str = Field(min_length=1, max_length=200)
    degree: str = Field(min_length=1, max_length=200)
    field: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    grade: str | None = Field(default=None, max_length=50)


class EducationUpdate(BaseModel):
    institution: str | None = Field(default=None, min_length=1, max_length=200)
    degree: str | None = Field(default=None, min_length=1, max_length=200)
    field: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    grade: str | None = Field(default=None, max_length=50)


class EducationOut(ORMModel, EducationIn):
    id: int


class ExperienceIn(BaseModel):
    role: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    bullets: list[str] = Field(default_factory=list, max_length=20)

    _b = field_validator("bullets")(_clean_list)


class ExperienceUpdate(BaseModel):
    role: str | None = Field(default=None, min_length=1, max_length=200)
    company: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    bullets: list[str] | None = Field(default=None, max_length=20)

    _b = field_validator("bullets")(lambda v: None if v is None else _clean_list(v))


class ExperienceOut(ORMModel, ExperienceIn):
    id: int


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: SkillCategory = "other"
    proficiency: Proficiency | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: SkillCategory | None = None
    proficiency: Proficiency | None = None


class SkillOut(ORMModel, SkillIn):
    id: int


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    tech_stack: list[str] = Field(default_factory=list, max_length=30)
    url: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None

    _t = field_validator("tech_stack")(_clean_list)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    tech_stack: list[str] | None = Field(default=None, max_length=30)
    url: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None

    _t = field_validator("tech_stack")(lambda v: None if v is None else _clean_list(v))


class ProjectOut(ORMModel, ProjectIn):
    id: int


class CertificationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)
    issue_date: date | None = None
    credential_url: str | None = Field(default=None, max_length=500)


class CertificationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)
    issue_date: date | None = None
    credential_url: str | None = Field(default=None, max_length=500)


class CertificationOut(ORMModel, CertificationIn):
    id: int
