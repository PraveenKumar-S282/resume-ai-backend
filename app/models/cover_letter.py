from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.job_analysis import LongText


class GeneratedCoverLetter(TimestampMixin, Base):
    __tablename__ = "generated_cover_letters"
    __table_args__ = (Index("ix_letters_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("job_analyses.id", ondelete="SET NULL"))
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("generated_resumes.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(LongText)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(10), default="draft", server_default="draft")
