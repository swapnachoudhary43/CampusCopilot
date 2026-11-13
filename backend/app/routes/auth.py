"""Registration, login, and the current user's profile."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db
from app.models.entities import User
from app.routes.serializers import user_out
from app.schemas.api import LoginRequest, PasswordChange, ProfileUpdate, RegisterRequest, TokenResponse
from app.core.throttle import login_allowed, record_login_failure, record_login_success
from app.services.audit import log_action

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(user: User) -> dict:
    return TokenResponse(
        access_token=create_access_token(user.id, int(user.token_version or 0)),
        user=user_out(user),
    ).model_dump()


@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(
        full_name=body.full_name.strip(),
        email=body.email,
        password_hash=hash_password(body.password),
        role="student",
        department=body.department,
        is_active=True,
    )
    db.add(user)
    db.flush()
    log_action(db, user_id=user.id, action="user_registered", entity_type="user", entity_id=str(user.id))
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    if not login_allowed(body.email):
        raise HTTPException(status_code=429, detail="Too many login attempts. Wait a few minutes and try again.")
    user = db.query(User).filter(User.email == body.email).first()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        record_login_failure(body.email)
        log_action(
            db,
            user_id=None,
            action="login_failed",
            entity_type="user",
            details="Failed login attempt.",
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    record_login_success(body.email)
    log_action(db, user_id=user.id, action="login", entity_type="user", entity_id=str(user.id))
    db.commit()
    return _token_response(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.department is not None:
        user.department = body.department.strip() or None
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/change-password")
def change_password(body: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="The current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    user.token_version = int(user.token_version or 0) + 1
    log_action(db, user_id=user.id, action="password_changed", entity_type="user", entity_id=str(user.id))
    db.commit()
    return {"detail": "Password updated."}
