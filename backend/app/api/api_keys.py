import secrets
import hashlib
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.api_key import ProjectApiKey
from ..models.project import Project, ProjectUser
from ..models.user import User
from .users import get_current_user

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None

    class Config:
        orm_mode = True


class ApiKeyCreated(ApiKeyResponse):
    key: str  # full key — shown ONLY on creation


# ── Helpers ────────────────────────────────────────────────────────────────────

def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _assert_member(project_id: int, user_id: int, db: Session) -> None:
    link = db.query(ProjectUser).filter(
        ProjectUser.project_id == project_id,
        ProjectUser.user_id == user_id,
    ).first()
    if not link:
        raise HTTPException(status_code=403, detail="Not a member of this project")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/{project_id}/api-keys", response_model=List[ApiKeyResponse])
def list_api_keys(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_member(project_id, current_user.id, db)
    return (
        db.query(ProjectApiKey)
        .filter(ProjectApiKey.project_id == project_id, ProjectApiKey.is_active == True)
        .order_by(ProjectApiKey.created_at.desc())
        .all()
    )


@router.post("/{project_id}/api-keys", response_model=ApiKeyCreated)
def create_api_key(
    project_id: int,
    body: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_member(project_id, current_user.id, db)

    raw = f"blv_{secrets.token_hex(24)}"   # 52-char key: blv_ + 48 hex chars
    prefix = raw[:12]                       # "blv_" + first 8 hex chars

    key = ProjectApiKey(
        project_id=project_id,
        name=body.name,
        key_hash=_hash_key(raw),
        key_prefix=prefix,
    )
    db.add(key)
    db.commit()
    db.refresh(key)

    return ApiKeyCreated(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        is_active=key.is_active,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        key=raw,
    )


@router.delete("/{project_id}/api-keys/{key_id}")
def delete_api_key(
    project_id: int,
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_member(project_id, current_user.id, db)
    key = db.query(ProjectApiKey).filter(
        ProjectApiKey.id == key_id,
        ProjectApiKey.project_id == project_id,
    ).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    db.delete(key)
    db.commit()
    return {"message": "Deleted"}


# ── Reusable auth dependency (used by /api/v1/* routes) ───────────────────────

def get_project_from_api_key(
    x_api_key: str,
    db: Session,
) -> Project:
    """Validate X-Api-Key header and return the associated Project."""
    hashed = _hash_key(x_api_key)
    key_row = db.query(ProjectApiKey).filter(
        ProjectApiKey.key_hash == hashed,
        ProjectApiKey.is_active == True,
    ).first()
    if not key_row:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    # Update last_used_at without blocking
    key_row.last_used_at = datetime.utcnow()
    db.commit()

    project = db.query(Project).filter(Project.id == key_row.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
