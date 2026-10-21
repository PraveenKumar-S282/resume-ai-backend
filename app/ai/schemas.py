"""Shapes the LLM must return. Everything is validated before use."""
from pydantic import BaseModel, Field


class JDExtraction(BaseModel):
    job_title: str = ""
    company: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_requirement: str | None = None
    keywords: list[str] = Field(default_factory=list)


class ExperienceDraft(BaseModel):
    id: int
    bullets: list[str] = Field(default_factory=list)


class ProjectDraft(BaseModel):
    id: int
    bullets: list[str] = Field(default_factory=list)


class ResumeDraft(BaseModel):
    summary: str = ""
    experience: list[ExperienceDraft] = Field(default_factory=list)
    projects: list[ProjectDraft] = Field(default_factory=list)  # most relevant first


class CoverLetterDraft(BaseModel):
    paragraphs: list[str] = Field(default_factory=list)
