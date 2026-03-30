# app/routes/webhook.py

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models_alerts import AlertHistory, ProjectHealthState
from app.services.teams_notification_service import TeamsNotificationService
from app.services.incident_service import IncidentService
from app.services.throttle_service import ThrottleService, EscalationService

router = APIRouter(prefix="/api/webhook", tags=["Webhooks"])

throttle   = ThrottleService()
escalation = EscalationService()

ESCALATION_DAYS = 3  # alert again if still AT RISK after 3 days


class GrafanaAlert(BaseModel):
    status:       str
    labels:       dict
    annotations:  dict
    generatorURL: Optional[str] = None
    fingerprint:  Optional[str] = None


class WebhookPayload(BaseModel):
    receiver:     str
    status:       str
    alerts:       List[GrafanaAlert]
    groupLabels:  Optional[dict] = {}
    commonLabels: Optional[dict] = {}


@router.post("/alert")
async def receive_alert(
    payload: WebhookPayload,
    db: Session = Depends(get_db),
):
    results  = []
    notifier = TeamsNotificationService()
    incident = IncidentService()

    for alert in payload.alerts:
        project_key = str(alert.labels.get("project_key", "UNKNOWN"))
        severity    = str(alert.labels.get("severity", "WARNING")).upper()
        summary     = str(alert.annotations.get("summary", "No summary"))
        description = str(alert.annotations.get("description", "No description"))
        status      = alert.status

        print(f"[WEBHOOK] {severity} | {status} | {project_key}: {summary}")

        # ── RESOLVED ──────────────────────────────────────────
        if status == "resolved":
            _handle_resolved(db, project_key, severity)
            throttle.clear(f"{project_key}:{severity}")
            escalation.clear_pending(project_key)

            # Update state to HEALTHY
            _update_health_state(db, project_key, "HEALTHY")
            results.append({"project_key": project_key, "action": "resolved"})
            continue

        # ── Get last known health state ────────────────────────
        last_state = db.query(ProjectHealthState).filter(
            ProjectHealthState.project_key == project_key
        ).first()

        incoming_health = "AT RISK" if severity == "CRITICAL" else "WARNING"
        last_health = last_state.health if last_state else None
        is_new_alert = last_health != incoming_health

        # ── Save to alert history ──────────────────────────────
        record = AlertHistory(
            project_key = project_key,
            severity    = severity,
            status      = "firing",
            summary     = summary,
            description = description,
            fired_at    = datetime.utcnow(),
        )
        db.add(record)
        db.flush()
        alert_id = int(record.id)

        # ── Check 3-day escalation ─────────────────────────────
        needs_escalation = False
        if last_state and last_state.alerted_at:
            days_since_alert = (datetime.utcnow() - last_state.alerted_at).days
            if days_since_alert >= ESCALATION_DAYS and not is_new_alert:
                needs_escalation = True
                print(f"[WEBHOOK] {project_key} unresolved for {days_since_alert} days — escalating")

        # ── CRITICAL ───────────────────────────────────────────
        if severity == "CRITICAL":
            if is_new_alert or needs_escalation:
                jira_ticket = incident.create_incident(
                    project_key = project_key,
                    summary     = f"[AUTO-INCIDENT] {summary}",
                    description = description,
                    severity    = severity,
                )

                record.jira_ticket    = jira_ticket
                record.teams_notified = True

                action_label = "escalation" if needs_escalation else "new"

                notifier.send_critical_alert(
                    project_key  = project_key,
                    summary      = summary,
                    description  = description,
                    jira_ticket  = jira_ticket,
                    is_escalation = needs_escalation,
                )

                _update_health_state(db, project_key, "AT RISK", alerted_now=True)

                print(f"[WEBHOOK] CRITICAL {action_label} alert sent for {project_key}")
                results.append({
                    "project_key": project_key,
                    "severity":    severity,
                    "action":      f"teams_notified ({action_label})",
                    "ticket":      jira_ticket,
                    "alert_id":    alert_id,
                })
            else:
                print(f"[WEBHOOK] CRITICAL skipped for {project_key} — no status change")
                results.append({"project_key": project_key, "action": "skipped_no_change"})

        # ── WARNING ────────────────────────────────────────────
        elif severity == "WARNING":
            if is_new_alert:
                record.teams_notified = True

                notifier.send_warning_alert(
                    project_key = project_key,
                    summary     = summary,
                    description = description,
                )

                escalation.set_pending(
                    project_key     = project_key,
                    alert_id        = alert_id,
                    timeout_seconds = 900,
                )

                _update_health_state(db, project_key, "WARNING", alerted_now=True)

                print(f"[WEBHOOK] WARNING new alert sent for {project_key}")
                results.append({
                    "project_key":  project_key,
                    "severity":     severity,
                    "action":       "teams_notified (new)",
                    "alert_id":     alert_id,
                })
            else:
                print(f"[WEBHOOK] WARNING skipped for {project_key} — no status change")
                results.append({"project_key": project_key, "action": "skipped_no_change"})

        db.commit()

    return JSONResponse(content={"processed": len(results), "results": results})


def _update_health_state(
    db: Session,
    project_key: str,
    health: str,
    alerted_now: bool = False,
):
    state = db.query(ProjectHealthState).filter(
        ProjectHealthState.project_key == project_key
    ).first()

    if state:
        state.health     = health
        state.updated_at = datetime.utcnow()
        if alerted_now:
            state.alerted_at = datetime.utcnow()
    else:
        state = ProjectHealthState(
            project_key = project_key,
            health      = health,
            updated_at  = datetime.utcnow(),
            alerted_at  = datetime.utcnow() if alerted_now else None,
        )
        db.add(state)


def _handle_resolved(db: Session, project_key: str, severity: str):
    record = (
        db.query(AlertHistory)
        .filter(
            AlertHistory.project_key == project_key,
            AlertHistory.severity    == severity,
            AlertHistory.status      == "firing",
        )
        .order_by(AlertHistory.fired_at.desc())
        .first()
    )
    if record:
        record.status      = "resolved"
        record.resolved_at = datetime.utcnow()
        db.commit()
        print(f"[WEBHOOK] Resolved alert for {project_key} ({severity})")


@router.post("/acknowledge/{alert_id}")
async def acknowledge_alert(
    alert_id: int,
    acknowledged_by: str = "engineer",
    db: Session = Depends(get_db),
):
    record = db.query(AlertHistory).filter(AlertHistory.id == alert_id).first()
    if not record:
        return JSONResponse(status_code=404, content={"error": "Alert not found"})

    record.acknowledged    = True
    record.acknowledged_by = acknowledged_by
    record.acknowledged_at = datetime.utcnow()
    db.commit()
    escalation.clear_pending(str(record.project_key))

    print(f"[WEBHOOK] Alert {alert_id} acknowledged by {acknowledged_by}")
    return {"message": f"Alert {alert_id} acknowledged", "project": record.project_key}


@router.get("/history")
async def alert_history(
    project_key: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(AlertHistory).order_by(AlertHistory.fired_at.desc())
    if project_key:
        query = query.filter(AlertHistory.project_key == project_key)
    records = query.limit(limit).all()
    return {"alerts": [r.to_dict() for r in records], "total": len(records)}