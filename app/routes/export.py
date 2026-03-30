import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.auth.permissions import require_permission
from app.services.services import fetch_dashboard_data

router = APIRouter(prefix="/api", tags=["Export"])


@router.get("/project/{project_key}/export/{export_format}")
def export_dashboard(
    project_key: str,
    export_format: str,
    days_back: int = Query(default=30),
    _user=Depends(require_permission("dashboard:view")),
):
    fmt = export_format.lower()
    if fmt not in ("csv", "json", "pdf", "excel"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown export format",
        )

    if fmt in ("pdf", "excel"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This export format is not implemented yet. Use CSV or JSON.",
        )

    data = fetch_dashboard_data(project_key, days_back)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No data for this project and time range.",
        )

    issues = list(data.get("df") or [])
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_key)

    if fmt == "json":
        payload = {
            "project_key": project_key,
            "days_back": days_back,
            "metrics": data.get("metrics"),
            "rules": data.get("rules"),
            "issues": issues,
        }
        body = json.dumps(payload, indent=2, default=str)
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}_export.json"'
            },
        )

    buf = io.StringIO()
    if issues:
        fieldnames = list(issues[0].keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)
    else:
        buf.write("no_issues\n")

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_export.csv"'
        },
    )
