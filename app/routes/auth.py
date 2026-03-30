from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth import jira_client
from app.auth.dependencies import get_current_user
from app.auth.jwt_handler import create_access_token
from app.auth.password_utils import hash_password, verify_password
from app.auth.permissions import get_user_permissions
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    id: int
    username: str
    email: str | None
    is_active: bool
    roles: list[str]
    permissions: list[str]


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User inactive",
        )

    token = create_access_token({"id": user.id, "username": user.username})
    return TokenResponse(access_token=token)


@router.post("/logout", response_model=MessageResponse)
def logout():
    return MessageResponse(message="Successfully logged out")


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Account created successfully", "username": new_user.username}


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    permissions = sorted(get_user_permissions(current_user))
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        roles=sorted(role.name for role in current_user.roles),
        permissions=permissions,
    )




