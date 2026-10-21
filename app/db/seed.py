from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.templates import TEMPLATE_DEFS
from app.models import DocumentTemplate


def seed_templates(db: Session) -> None:
    """Idempotent. Run on startup so a fresh database always has the three templates."""
    existing = {t.key for t in db.scalars(select(DocumentTemplate))}
    for t in TEMPLATE_DEFS:
        if t["key"] not in existing:
            db.add(DocumentTemplate(key=t["key"], name=t["name"], description=t["description"], config=t["config"], is_active=True))
    db.commit()
