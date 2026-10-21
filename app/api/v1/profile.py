from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models import CandidateProfile, Certification, Education, Project, Skill, User, WorkExperience
from app.schemas import profile as S
from app.services.profile_service import completeness, get_or_create_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=S.ProfileOut, summary="Get my profile")
def get_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_or_create_profile(db, user)


@router.put("", response_model=S.ProfileOut, summary="Update my profile details")
def put_profile(data: S.ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = get_or_create_profile(db, user)
    for k, v in data.model_dump().items():
        setattr(profile, k, v)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/completeness", response_model=S.Completeness, summary="Profile completeness")
def get_completeness(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return completeness(get_or_create_profile(db, user))


def _check_skill_unique(db: Session, profile: CandidateProfile, name: str, exclude_id: int | None = None) -> None:
    q = select(Skill.id).where(Skill.profile_id == profile.id, func.lower(Skill.name) == name.lower())
    if exclude_id:
        q = q.where(Skill.id != exclude_id)
    if db.scalar(q) is not None:
        raise AppError(409, "DUPLICATE_SKILL", f"'{name}' is already in your skills.")


def _add_section(path: str, label: str, Model, In, Update, Out, unique_hook=None) -> None:
    def _get(db: Session, profile: CandidateProfile, item_id: int):
        item = db.scalar(select(Model).where(Model.id == item_id, Model.profile_id == profile.id))
        if item is None:
            raise AppError(404, "NOT_FOUND", f"{label.capitalize()} not found.")
        return item

    @router.get(f"/{path}", response_model=list[Out], name=f"list_{path}", summary=f"List {label}s")
    def list_items(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        profile = get_or_create_profile(db, user)
        return list(db.scalars(select(Model).where(Model.profile_id == profile.id).order_by(Model.id)))

    @router.post(f"/{path}", response_model=Out, status_code=201, name=f"create_{path}", summary=f"Add {label}")
    def create_item(data: In, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        profile = get_or_create_profile(db, user)
        if unique_hook:
            unique_hook(db, profile, data.name)
        item = Model(profile_id=profile.id, **data.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @router.patch(f"/{path}/{{item_id}}", response_model=Out, name=f"update_{path}", summary=f"Edit {label}")
    def update_item(item_id: int, data: Update, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        profile = get_or_create_profile(db, user)
        item = _get(db, profile, item_id)
        changes = data.model_dump(exclude_unset=True)
        for col, val in changes.items():
            if val is None and not Model.__table__.columns[col].nullable:
                raise AppError(422, "VALIDATION_ERROR", "Some fields are invalid.", [{"field": col, "issue": "This field cannot be empty."}])
        if unique_hook and "name" in changes:
            unique_hook(db, profile, changes["name"], exclude_id=item.id)
        for col, val in changes.items():
            setattr(item, col, val)
        db.commit()
        db.refresh(item)
        return item

    @router.delete(f"/{path}/{{item_id}}", status_code=204, name=f"delete_{path}", summary=f"Delete {label}")
    def delete_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        profile = get_or_create_profile(db, user)
        db.delete(_get(db, profile, item_id))
        db.commit()
        return Response(status_code=204)


_add_section("education", "education entry", Education, S.EducationIn, S.EducationUpdate, S.EducationOut)
_add_section("experience", "work experience entry", WorkExperience, S.ExperienceIn, S.ExperienceUpdate, S.ExperienceOut)
_add_section("skills", "skill", Skill, S.SkillIn, S.SkillUpdate, S.SkillOut, unique_hook=_check_skill_unique)
_add_section("projects", "project", Project, S.ProjectIn, S.ProjectUpdate, S.ProjectOut)
_add_section("certifications", "certification", Certification, S.CertificationIn, S.CertificationUpdate, S.CertificationOut)
