# app/routes/webhook.py
# Receives ONE batched payload from Alertmanager and sends a single consolidated digest

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models_alerts import AlertHistory
from app.services.teams_notification_service import TeamsNotificationService
from app.services.incident_service import IncidentService
from app.services.throttle_service import ThrottleService, EscalationService

router = APIRouter(prefix="/api/webhook", tags=["Webhooks"])

throttle   = ThrottleService()
escalation = EscalationService()

DIGEST_THROTTLE_SECONDS = 21600   # 6 hours — one digest per cycle max
RECALL_AFTER_SECONDS    = 86400   # re-alert if still critical and unacked after 24h


# ── Payload schemas ────────────────────────────────────────────
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


# ── Main webhook — consolidated digest ────────────────────────
@router.post("/alert")
async def receive_alert(
    payload: WebhookPayload,
    db: Session = Depends(get_db),
):
    notifier = TeamsNotificationService()
    incident = IncidentService()

    firing_alerts   = [a for a in payload.alerts if a.status == "firing"]
    resolved_alerts = [a for a in payload.alerts if a.status == "resolved"]

    # ── Handle resolved alerts ─────────────────────────────────
    for alert in resolved_alerts:
        project_key = str(alert.labels.get("project_key", "UNKNOWN"))
        severity    = str(alert.labels.get("severity", "WARNING")).upper()
        _handle_resolved(db, project_key, severity)
        throttle.clear(f"{project_key}:{severity}")
        escalation.clear_pending(project_key)
        print(f"[WEBHOOK] Resolved {severity} | {project_key}")

    if not firing_alerts:
        return JSONResponse(content={"processed": len(resolved_alerts), "action": "resolved_only"})

    # ── Deduplicate: save all firing alerts to DB ──────────────
    saved_projects = []
    for alert in firing_alerts:
        project_key = str(alert.labels.get("project_key", "UNKNOWN"))
        severity    = str(alert.labels.get("severity", "WARNING")).upper()
        summary     = str(alert.annotations.get("summary", ""))
        description = str(alert.annotations.get("description", ""))

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

        saved_projects.append({
            "project_key": project_key,
            "severity":    severity,
            "summary":     summary,
            "description": description,
            "alert_id":    int(record.id),
        })

        # Auto-create Jira ticket for CRITICAL if not throttled
        if severity == "CRITICAL":
            throttle_key = f"{project_key}:CRITICAL:ticket"
            unacked_old = (
                db.query(AlertHistory)
                .filter(
                    AlertHistory.project_key  == project_key,
                    AlertHistory.severity     == "CRITICAL",
                    AlertHistory.status       == "firing",
                    AlertHistory.acknowledged == False,
                    AlertHistory.fired_at     <= datetime.utcnow() - timedelta(seconds=RECALL_AFTER_SECONDS),
                )
                .first()
            )
            if unacked_old:
                throttle.clear(throttle_key)

            if not throttle.is_throttled(throttle_key, seconds=RECALL_AFTER_SECONDS):
                throttle.mark(throttle_key, seconds=RECALL_AFTER_SECONDS)
                jira_ticket = incident.create_incident(
                    project_key = project_key,
                    summary     = f"[AUTO-INCIDENT] {summary}",
                    description = description,
                    severity    = severity,
                )
                record.jira_ticket    = jira_ticket
                record.teams_notified = True
                print(f"[WEBHOOK] Created Jira ticket {jira_ticket} for {project_key}")

    db.commit()

    # ── Send ONE consolidated Teams digest ─────────────────────
    digest_key = "portfolio:digest"
    unacked_critical_old = (
        db.query(AlertHistory)
        .filter(
            AlertHistory.severity     == "CRITICAL",
            AlertHistory.status       == "firing",
            AlertHistory.acknowledged == False,
            AlertHistory.fired_at     <= datetime.utcnow() - timedelta(seconds=RECALL_AFTER_SECONDS),
        )
        .first()
    )
    if unacked_critical_old:
        throttle.clear(digest_key)

    if not throttle.is_throttled(digest_key, seconds=DIGEST_THROTTLE_SECONDS):
        throttle.mark(digest_key, seconds=DIGEST_THROTTLE_SECONDS)

        # Enrich with latest metrics from Prometheus cache if available
        enriched = _enrich_with_metrics(saved_projects)
        notifier.send_consolidated_digest(enriched)
        print(f"[WEBHOOK] Sent consolidated digest — {len(saved_projects)} projects")
    else:
        print(f"[WEBHOOK] Digest throttled — already sent within last 6h")

    return JSONResponse(content={
        "processed": len(saved_projects),
        "action": "consolidated_digest",
        "projects": [p["project_key"] for p in saved_projects],
    })


def _enrich_with_metrics(projects: list) -> list:
    """Try to add stale/wip data from backend cache for richer digest."""
    try:
        from app.services.services import _DASHBOARD_CACHE
        import time
        now = time.time()
        for p in projects:
            key = (p["project_key"], 30)
            cached = _DASHBOARD_CACHE.get(key)
            if cached and cached["expires_at"] > now:
                m = cached["payload"].get("metrics", {})
                p["stale"]   = m.get("stale_in_progress_count", 0)
                p["wip_pct"] = round(m.get("wip_ratio", 0) * 100, 1)
                p["total"]   = m.get("total", 0)
            else:
                p["stale"]   = None
                p["wip_pct"] = None
                p["total"]   = None
    except Exception as e:
        print(f"[WEBHOOK] Metrics enrichment failed: {e}")
    return projects


# ── Acknowledge ────────────────────────────────────────────────
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


# ── Alert history ──────────────────────────────────────────────
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


# ── Helper ─────────────────────────────────────────────────────
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