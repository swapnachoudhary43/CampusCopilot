"""Administrator user management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.security import hash_password
from app.database.session import get_db
from app.models.entities import User
from app.routes.serializers import user_out
from app.schemas.api import AdminUserCreate, AdminUserUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [user_out(user) for user in users]


@router.get("/staff")
def list_staff(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    users = (
        db.query(User)
        .filter(User.role.in_(("faculty", "admin")), User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )
    return [user_out(user) for user in users]


@router.post("", status_code=201)
def create_user(
    body: AdminUserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(
        full_name=body.full_name.strip(),
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        department=body.department,
        is_active=True,
    )
    db.add(user)
    db.flush()
    log_action(
        db,
        user_id=actor.id,
        action="user_created",
        entity_type="user",
        entity_id=str(user.id),
        details=body.role,
    )
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if body.is_active is False and user.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.department is not None:
        user.department = body.department
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    log_action(
        db,
        user_id=actor.id,
        action="user_updated",
        entity_type="user",
        entity_id=str(user.id),
        details=user.role,
    )
    db.commit()
    db.refresh(user)
    return user_out(user)
