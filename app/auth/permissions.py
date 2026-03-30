from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.db.models import Role, User
from app.db.session import get_db


def get_user_with_access_graph(db: Session, user_id: int) -> User | None:
    return (
        db.query(User)
        .options(
            joinedload(User.roles).joinedload(Role.permissions)
        )
        .filter(User.id == user_id)
        .first()
    )


def get_user_permissions(user: User) -> set[str]:
    return {
        permission.name
        for role in user.roles
        for permission in role.permissions
    }


def has_permission(user: User, permission_name: str) -> bool:
    return permission_name in get_user_permissions(user)


def require_permission(permission_name: str):
    def checker(
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        user = get_user_with_access_graph(db, current_user.id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive or invalid user",
            )

        if not has_permission(user, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return user

    return checker
