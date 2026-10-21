from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

LongText = Text().with_variant(MEDIUMTEXT(), "mysql")


class JobAnalysis(TimestampMixin, Base):
    __tablename__ = "job_analyses"
    __table_args__ = (Index("ix_job_analyses_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_title: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200))
    jd_text: Mapped[str] = mapped_column(LongText)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    experience_requirement: Mapped[str | None] = mapped_column(String(200))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    match_result: Mapped[dict] = mapped_column(JSON, default=dict)
