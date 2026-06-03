# backend/app/api/users.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from math import ceil
from app.database import get_db
from app.models.user import User
from app.models.contact import Contact
from app.models.login_history import LoginHistory
from app.core.deps import require_admin
from app.core.security import hash_password, blacklist_user_tokens, remove_user_from_blacklist
from app.core.redis_client import redis_client
from app.schemas.user import UserCreate, UserUpdate, UserOut, ResetPasswordRequest
from app.schemas.auth import LoginHistoryOut

router = APIRouter(prefix="/api/users", tags=["users"])

VALID_USER_SORT_FIELDS = {"email", "full_name", "role", "created_at"}


@router.get("")
def list_users(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if org_id is not None:
        q = q.filter(User.org_id == org_id)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    if search:
        term = f"%{search}%"
        q = q.filter(or_(User.email.ilike(term), User.full_name.ilike(term)))
    if sort not in VALID_USER_SORT_FIELDS:
        sort = "created_at"
    sort_col = getattr(User, sort, User.created_at)
    q = q.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    total = q.count()
    users_page = q.offset((page - 1) * per_page).limit(per_page).all()
    user_ids = [u.id for u in users_page]
    contact_map = {}
    if user_ids:
        linked = db.query(Contact).filter(Contact.user_id.in_(user_ids)).all()
        contact_map = {c.user_id: c for c in linked}
    out_items = []
    for u in users_page:
        c = contact_map.get(u.id)
        obj = UserOut.model_validate(u)
        obj.linked_contact_id = c.id if c else None
        obj.linked_contact_name = c.name if c else None
        out_items.append(obj)
    return {
        "items": out_items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total > 0 else 1,
    }


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already exists")
    data = payload.model_dump()
    data["password_hash"] = hash_password(data.pop("password"))
    data["must_change_password"] = True  # always force password change on creation
    new_user = User(**data)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    updates = payload.model_dump(exclude_none=True)

    # Handle activation state changes
    if "is_active" in updates:
        was_active = target.is_active
        will_be_active = updates["is_active"]
        if was_active and not will_be_active:
            # Deactivating: blacklist all tokens immediately
            blacklist_user_tokens(user_id, redis_client)
        elif not was_active and will_be_active:
            # Reactivating: clear blacklist
            remove_user_from_blacklist(user_id, redis_client)

    for k, v in updates.items():
        setattr(target, k, v)
    db.commit()
    db.refresh(target)
    return target


@router.post("/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin resets a user's password and forces re-login + password change."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    target.password_hash = hash_password(payload.new_password)
    target.must_change_password = True
    db.commit()
    # Force re-login by blacklisting existing tokens
    blacklist_user_tokens(user_id, redis_client)
    db.refresh(target)
    return target


@router.get("/{user_id}/login-history", response_model=List[LoginHistoryOut])
def get_login_history(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get last 50 login events for a user (admin only)."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    events = (
        db.query(LoginHistory)
        .filter(LoginHistory.user_id == user_id)
        .order_by(LoginHistory.created_at.desc())
        .limit(50)
        .all()
    )
    return events
