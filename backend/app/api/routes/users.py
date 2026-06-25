from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user
from app.core.database import get_db
from app.core.security import hash_password
from app.models import User
from app.schemas.auth import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

VALID_ROLES = frozenset({"admin", "user"})


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    return [UserOut.model_validate(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    role = payload.role if payload.role in VALID_ROLES else "user"
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] != user.email:
        clash = db.execute(select(User).where(User.email == data["email"])).scalar_one_or_none()
        if clash:
            raise HTTPException(status_code=409, detail="Email is already in use.")
        user.email = data["email"]

    if "name" in data:
        user.name = data["name"]

    if "role" in data:
        new_role = data["role"]
        if new_role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'.")
        if user.id == admin.id and new_role != "admin":
            raise HTTPException(status_code=400, detail="You cannot remove your own admin role.")
        user.role = new_role

    if "password" in data and data["password"]:
        user.password_hash = hash_password(data["password"])

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    admin_count = db.scalar(select(func.count()).select_from(User).where(User.role == "admin"))
    if user.role == "admin" and admin_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last admin account.")

    db.delete(user)
    db.commit()
    return None
