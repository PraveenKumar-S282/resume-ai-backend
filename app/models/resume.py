from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class GeneratedResume(TimestampMixin, Base):
    __tablename__ = "generated_resumes"
    __table_args__ = (Index("ix_resumes_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("job_analyses.id", ondelete="SET NULL"))
    template_id: Mapped[int] = mapped_column(ForeignKey("document_templates.id"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(10), default="draft", server_default="draft")

    template = relationship("DocumentTemplate", lazy="joined")

    @property
    def template_key(self) -> str:
        return self.template.key if self.template else "classic"
