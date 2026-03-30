import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.auth.permissions import require_permission

router = APIRouter(prefix="/api", tags=["Snapshots"])

_store_path = Path(__file__).resolve().parent.parent.parent / "data" / "snapshots.json"
_lock = Lock()


class SnapshotCreate(BaseModel):
    project: str
    health: str
    metrics: dict = Field(default_factory=dict)
    rules: dict = Field(default_factory=dict)


def _read_all() -> list[dict]:
    if not _store_path.exists():
        return []
    with open(_store_path, encoding="utf-8") as f:
        return json.load(f)


def _write_all(rows: list[dict]) -> None:
    _store_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _store_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
        f.flush()
    tmp.replace(_store_path)


@router.get("/snapshots")
def list_snapshots(_user=Depends(require_permission("dashboard:view"))):
    with _lock:
        return _read_all()


@router.post("/snapshots", status_code=status.HTTP_201_CREATED)
def save_snapshot(
    payload: SnapshotCreate,
    _user=Depends(require_permission("dashboard:view")),
):
    entry = {
        "timestamp": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "project": payload.project,
        "health": payload.health,
        "metrics": payload.metrics,
        "rules": payload.rules,
    }
    with _lock:
        rows = _read_all()
        rows.append(entry)
        _write_all(rows)
    return entry


@router.delete("/snapshots")
def clear_snapshots(_user=Depends(require_permission("dashboard:view"))):
    with _lock:
        if _store_path.exists():
            _store_path.unlink()
    return {"message": "Snapshots cleared"}
