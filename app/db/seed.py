# app/db/seed.py
"""
Idempotent seed for roles and permissions.
Safe to call on every startup — uses get-or-create, never duplicates.
"""
from app.db.models import Permission, Role
from app.db.session import SessionLocal

# ── Permission → Roles mapping ─────────────────────────────────────────────
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [
        "dashboard:view",
        "project:view",
        "project:assign",
        "project:create",
        "user:manage",
    ],
    "manager": [
        "dashboard:view",
        "project:view",
        "project:assign",
        "project:create",
    ],
    "user": [
        "dashboard:view",
        "project:view",
    ],
}


def seed_roles_and_permissions() -> None:
    """Create all roles and permissions if they don't already exist."""
    db = SessionLocal()
    try:
        # ── 1. Ensure all permissions exist ───────────────────────────────
        all_perm_names: set[str] = {
            p for perms in ROLE_PERMISSIONS.values() for p in perms
        }
        perm_map: dict[str, Permission] = {}
        for name in all_perm_names:
            perm = db.query(Permission).filter(Permission.name == name).first()
            if not perm:
                perm = Permission(name=name)
                db.add(perm)
                db.flush()
            perm_map[name] = perm

        # ── 2. Ensure all roles exist and carry the right permissions ──────
        for role_name, perm_names in ROLE_PERMISSIONS.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(name=role_name)
                db.add(role)
                db.flush()

            # Sync permissions (add missing ones, keep extras if any)
            existing = {p.name for p in role.permissions}
            for pname in perm_names:
                if pname not in existing:
                    role.permissions.append(perm_map[pname])

        db.commit()
        print("✅ Roles & permissions seeded successfully.")
    except Exception as exc:
        db.rollback()
        print(f"⚠️  Seed failed: {exc}")
    finally:
        db.close()
