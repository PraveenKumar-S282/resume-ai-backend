from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DocumentTemplate(TimestampMixin, Base):
    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(String(200))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
