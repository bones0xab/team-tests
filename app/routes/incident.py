from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models_alerts import AlertHistory
from app.services.incident_service import IncidentService
from app.services.throttle_service import EscalationService
from datetime import datetime

router = APIRouter(prefix="/api/incident", tags=["Incident"])
esc = EscalationService()

@router.get("/create")
def create_incident_from_teams(
    project: str = Query(...),
    db: Session = Depends(get_db),
):
    """Called when engineer clicks 'Create Incident' in Teams WARNING card."""
    alert = (
        db.query(AlertHistory)
        .filter(AlertHistory.project_key == project, AlertHistory.status == "firing")
        .order_by(AlertHistory.fired_at.desc())
        .first()
    )
    if not alert:
        return {"error": "No active alert found for this project"}

    incident = IncidentService()
    ticket = incident.create_incident(
        project_key=project,
        summary=f"[MANUAL] {alert.summary}",
        description=str(alert.description or ""),
        severity="WARNING",
    )
    alert.jira_ticket = ticket
    alert.acknowledged = True
    alert.acknowledged_by = "teams_card"
    alert.acknowledged_at = datetime.utcnow()
    db.commit()
    esc.clear_pending(project)

    return {"message": "Incident created", "ticket": ticket, "project": project}


@router.get("/dismiss")
def dismiss_alert_from_teams(
    project: str = Query(...),
    db: Session = Depends(get_db),
):
    """Called when engineer clicks 'Dismiss' in Teams WARNING card."""
    alert = (
        db.query(AlertHistory)
        .filter(AlertHistory.project_key == project, AlertHistory.status == "firing")
        .order_by(AlertHistory.fired_at.desc())
        .first()
    )
    if not alert:
        return {"error": "No active alert found"}

    alert.acknowledged = True
    alert.acknowledged_by = "dismissed_via_teams"
    alert.acknowledged_at = datetime.utcnow()
    alert.status = "dismissed"
    db.commit()
    esc.clear_pending(project)

    return {"message": "Alert dismissed", "project": project}