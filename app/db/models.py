# app/db/models.py

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Table, Text, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# =========================
# Association Tables
# =========================

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


# =========================
# RBAC Models
# =========================

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    permissions: Mapped[List["Permission"]] = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )
    users: Mapped[List["User"]] = relationship(
        "User", secondary=user_roles, back_populates="roles"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    roles: Mapped[List[Role]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )


# =========================
# User Model
# =========================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)

    roles: Mapped[List[Role]] = relationship(
        "Role", secondary=user_roles, back_populates="users"
    )


# =========================
# Project Model
# =========================

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jira_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    jira_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    project_type: Mapped[Optional[str]] = mapped_column(String)
    category_name: Mapped[Optional[str]] = mapped_column(String)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    issues: Mapped[List["Issue"]] = relationship(
        "Issue",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# =========================
# Issue Model
# =========================

class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jira_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    jira_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status_canonical: Mapped[Optional[str]] = mapped_column(String, index=True)
    assignee_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    assignee_name: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    project: Mapped[Project] = relationship("Project", back_populates="issues")