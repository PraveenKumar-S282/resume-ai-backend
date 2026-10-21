from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class CandidateProfile(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    headline: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(30))
    location: Mapped[str | None] = mapped_column(String(120))
    summary: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    github_url: Mapped[str | None] = mapped_column(String(500))
    portfolio_url: Mapped[str | None] = mapped_column(String(500))
    achievements: Mapped[list] = mapped_column(JSON, default=list)

    user = relationship("User", back_populates="profile")
    education = relationship("Education", cascade="all, delete-orphan", passive_deletes=True, order_by="Education.sort_order, Education.id")
    experience = relationship("WorkExperience", cascade="all, delete-orphan", passive_deletes=True, order_by="WorkExperience.sort_order, WorkExperience.id")
    skills = relationship("Skill", cascade="all, delete-orphan", passive_deletes=True, order_by="Skill.id")
    projects = relationship("Project", cascade="all, delete-orphan", passive_deletes=True, order_by="Project.sort_order, Project.id")
    certifications = relationship("Certification", cascade="all, delete-orphan", passive_deletes=True, order_by="Certification.id")


class Education(TimestampMixin, Base):
    __tablename__ = "education"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    institution: Mapped[str] = mapped_column(String(200))
    degree: Mapped[str] = mapped_column(String(200))
    field: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    grade: Mapped[str | None] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class WorkExperience(TimestampMixin, Base):
    __tablename__ = "work_experience"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    bullets: Mapped[list] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_skill_profile_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20), default="other")
    proficiency: Mapped[str | None] = mapped_column(String(20))


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[list] = mapped_column(JSON, default=list)
    url: Mapped[str | None] = mapped_column(String(500))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Certification(TimestampMixin, Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    issuer: Mapped[str | None] = mapped_column(String(200))
    issue_date: Mapped[date | None] = mapped_column(Date)
    credential_url: Mapped[str | None] = mapped_column(String(500))
