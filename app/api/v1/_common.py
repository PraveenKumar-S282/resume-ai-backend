import re

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import DocumentTemplate

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def get_template(db: Session, key: str) -> DocumentTemplate:
    t = db.scalar(select(DocumentTemplate).where(DocumentTemplate.key == key, DocumentTemplate.is_active.is_(True)))
    if t is None:
        raise AppError(422, "INVALID_TEMPLATE", f"Unknown template '{key}'.", [{"field": "template_key", "issue": "Choose classic, modern or compact."}])
    return t


def file_response(data: bytes, fmt: str, title: str) -> Response:
    name = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()[:80] or "document"
    return Response(
        content=data, media_type=PDF if fmt == "pdf" else DOCX,
        headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"', "Cache-Control": "no-store"},
    )


def require_analysis(db: Session, analysis_id: int | None):
    from app.models import JobAnalysis

    a = db.get(JobAnalysis, analysis_id) if analysis_id else None
    if a is None:
        raise AppError(422, "ANALYSIS_MISSING", "The job analysis this document was based on has been deleted. Create a new analysis to continue.")
    return a
