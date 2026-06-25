from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models import User
from app.schemas.auth import UserCreate, UserList, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _count_admins(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0


@router.get("", response_model=UserList)
def list_users(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    users = db.execute(select(User).order_by(User.name)).scalars().all()
    return UserList(items=[UserOut.model_validate(u) for u in users], total=len(users))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
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
        role=payload.role,
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
    current_user: User = Depends(get_current_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] != user.email:
        clash = db.execute(select(User).where(User.email == data["email"])).scalar_one_or_none()
        if clash:
            raise HTTPException(status_code=409, detail="A user with this email already exists.")

    if data.get("role") == "user" and user.role == "admin":
        if _count_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last admin.")

    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))

    for key, value in data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.role == "admin" and _count_admins(db) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last admin.")

    db.delete(user)
    db.commit()
    return None
