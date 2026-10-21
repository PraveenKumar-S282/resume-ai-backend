"""Resume content, cover letters, generation preferences, analyses."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ORMModel


# ---------- preferences ----------
class Preferences(BaseModel):
    tone: Literal["professional", "confident", "friendly"] = "professional"
    length: Literal["one_page", "detailed"] = "one_page"
    emphasis: list[Literal["skills", "projects", "experience", "education"]] = Field(default_factory=lambda: ["skills", "projects"])


# ---------- resume content (the single source of truth for preview, DOCX and PDF) ----------
class Link(BaseModel):
    label: str = ""
    url: str = ""


class Header(BaseModel):
    name: str = ""
    headline: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[Link] = Field(default_factory=list)


class SkillGroup(BaseModel):
    category: str = ""
    items: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    role: str = ""
    company: str = ""
    location: str | None = None
    start: str | None = None
    end: str | None = None
    bullets: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    title: str = ""
    tech: list[str] = Field(default_factory=list)
    url: str | None = None
    bullets: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    dates: str | None = None
    grade: str | None = None


class CertificationItem(BaseModel):
    name: str = ""
    issuer: str | None = None
    date: str | None = None


class ResumeContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    header: Header = Field(default_factory=Header)
    summary: str = ""
    skills: list[SkillGroup] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)


# ---------- requests ----------
class GenerateResumeIn(BaseModel):
    template_key: str = "classic"
    preferences: Preferences = Field(default_factory=Preferences)


class GenerateCoverLetterIn(BaseModel):
    resume_id: int | None = None
    preferences: Preferences = Field(default_factory=Preferences)


class ResumeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    template_key: str | None = None
    content: ResumeContent | None = None
    status: Literal["draft", "saved"] | None = None


class CoverLetterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=20000)
    status: Literal["draft", "saved"] | None = None


class AnalysisIn(BaseModel):
    jd_text: str

    @field_validator("jd_text")
    @classmethod
    def _length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 100:
            raise ValueError("Paste the full job description (at least 100 characters).")
        if len(v) > 15000:
            raise ValueError("The job description is too long. Keep it under 15,000 characters.")
        return v


# ---------- responses ----------
class ResumeOut(ORMModel):
    id: int
    analysis_id: int | None
    template_key: str
    title: str
    status: str
    version: int
    content: ResumeContent
    preferences: dict
    scores: dict
    created_at: datetime
    updated_at: datetime


class CoverLetterOut(ORMModel):
    id: int
    analysis_id: int | None
    resume_id: int | None
    title: str
    status: str
    version: int
    content: str
    preferences: dict
    created_at: datetime
    updated_at: datetime


class DocRef(BaseModel):
    id: int
    title: str


class AnalysisDocuments(BaseModel):
    resumes: list[DocRef] = Field(default_factory=list)
    cover_letters: list[DocRef] = Field(default_factory=list)


class AnalysisOut(ORMModel):
    id: int
    job_title: str | None
    company: str | None
    jd_text: str
    required_skills: list[str]
    preferred_skills: list[str]
    experience_requirement: str | None
    keywords: list[str]
    match_result: dict
    created_at: datetime
    documents: AnalysisDocuments = Field(default_factory=AnalysisDocuments)


class AnalysisSummary(BaseModel):
    id: int
    job_title: str | None
    company: str | None
    keyword_score: float | None
    created_at: datetime


class DocumentListItem(BaseModel):
    id: int
    type: Literal["resume", "cover_letter"]
    title: str
    status: str
    created_at: datetime


class TemplateOut(ORMModel):
    key: str
    name: str
    description: str | None


class Suggestion(BaseModel):
    message: str
    priority: Literal["high", "medium", "low"] = "medium"


class ImproveOut(BaseModel):
    scores: dict
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[Suggestion]


class DashboardOut(BaseModel):
    profile_completeness: int
    counts: dict
    average_keyword_score: float | None
    recent: list[DocumentListItem]
