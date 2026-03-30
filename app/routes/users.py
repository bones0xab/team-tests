from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session, joinedload

from app.auth.password_utils import hash_password
from app.auth.permissions import get_user_permissions, require_permission
from app.db.models import Role, User
from app.db.session import get_db

router = APIRouter(prefix="/api/admin", tags=["Admin Users"])


class RoleOut(BaseModel):
    id: int
    name: str
    permissions: list[str]


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    is_active: bool
    created_at: str
    roles: list[str]
    role_ids: list[int]
    permissions: list[str]


class UserCreate(BaseModel):
    username: str
    email: EmailStr | None = None
    password: str
    role_id: int
    is_active: bool = True


class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    role_id: int | None = None
    is_active: bool | None = None


class UserStatusUpdate(BaseModel):
    is_active: bool


def _serialize_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else "",
        roles=sorted(role.name for role in user.roles),
        role_ids=sorted(role.id for role in user.roles),
        permissions=sorted(get_user_permissions(user)),
    )


def _get_user_with_relations(db: Session, user_id: int) -> User | None:
    return (
        db.query(User)
        .options(joinedload(User.roles).joinedload(Role.permissions))
        .filter(User.id == user_id)
        .first()
    )


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    _current=Depends(require_permission("user:manage")),
):
    roles = (
        db.query(Role)
        .options(joinedload(Role.permissions))
        .order_by(Role.name.asc())
        .all()
    )

    return [
        RoleOut(
            id=role.id,
            name=role.name,
            permissions=sorted(permission.name for permission in role.permissions),
        )
        for role in roles
    ]


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _current=Depends(require_permission("user:manage")),
):
    users = (
        db.query(User)
        .options(joinedload(User.roles).joinedload(Role.permissions))
        .order_by(User.id.asc())
        .all()
    )
    return [_serialize_user(user) for user in users]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _current=Depends(require_permission("user:manage")),
):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    if payload.email and db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    role = db.query(Role).filter(Role.id == payload.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
    )
    user.roles = [role]

    db.add(user)
    db.commit()

    created = _get_user_with_relations(db, user.id)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to load created user")

    return _serialize_user(created)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage")),
):
    user = _get_user_with_relations(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.username and payload.username != user.username:
        exists = db.query(User).filter(User.username == payload.username).first()
        if exists:
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = payload.username

    if payload.email is not None and payload.email != user.email:
        exists = db.query(User).filter(User.email == payload.email).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = payload.email

    if payload.password:
        user.password_hash = hash_password(payload.password)

    if payload.is_active is not None:
        if user.id == current_user.id and payload.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate yourself")
        user.is_active = payload.is_active

    if payload.role_id is not None:
        role = db.query(Role).filter(Role.id == payload.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        user.roles = [role]

    db.commit()

    refreshed = _get_user_with_relations(db, user.id)
    if not refreshed:
        raise HTTPException(status_code=500, detail="Failed to load updated user")

    return _serialize_user(refreshed)


@router.patch("/users/{user_id}/status", response_model=UserOut)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage")),
):
    user = _get_user_with_relations(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")

    user.is_active = payload.is_active
    db.commit()

    refreshed = _get_user_with_relations(db, user.id)
    if not refreshed:
        raise HTTPException(status_code=500, detail="Failed to load updated user")

    return _serialize_user(refreshed)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")

    db.delete(user)
    db.commit()

    return None
