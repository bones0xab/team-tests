from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models_alerts import AlertHistory
from app.db.session import get_db
from app.services.incident_service import IncidentService
from app.services.teams_notification_service import TeamsNotificationService
from app.services.throttle_service import (
    EscalationService,
    ThrottleService,
    _USE_REDIS,
    _redis_client,
)

router = APIRouter(prefix="/api/webhook", tags=["Webhooks"])

throttle   = ThrottleService()
escalation = EscalationService()

DIGEST_THROTTLE_SECONDS = 21600   # 6 hours
RECALL_AFTER_SECONDS    = 86400   # 24 hours
ACCUMULATE_WINDOW       = 120     # 2 minutes


# ── Schemas ───────────────────────────────────────────────────────────────────

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


# ── Main endpoint ─────────────────────────────────────────────────────────────

@router.post("/alert")
async def receive_alert(
    payload: WebhookPayload,
    db: Session = Depends(get_db),
):
    notifier = TeamsNotificationService()
    incident = IncidentService()

    firing_alerts   = [a for a in payload.alerts if a.status == "firing"]
    resolved_alerts = [a for a in payload.alerts if a.status == "resolved"]

    # ── Resolutions ───────────────────────────────────────────────────────────
    for alert in resolved_alerts:
        project_key = str(alert.labels.get("project_key", "UNKNOWN"))
        severity    = str(alert.labels.get("severity", "WARNING")).upper()
        _handle_resolved(db, project_key, severity)
        throttle.clear(f"{project_key}:{severity}:ticket")
        escalation.clear_pending(project_key)
        print(f"[WEBHOOK] Resolved {severity} | {project_key}")

    if not firing_alerts:
        return JSONResponse(content={"processed": len(resolved_alerts), "action": "resolved_only"})

    # ── Save alerts + Jira tickets ────────────────────────────────────────────
    saved_projects: List[dict] = []

    for alert in firing_alerts:
        project_key = str(alert.labels.get("project_key", "UNKNOWN"))
        severity    = str(alert.labels.get("severity", "WARNING")).upper()
        summary     = str(alert.annotations.get("summary", ""))
        description = str(alert.annotations.get("description", ""))

        record = AlertHistory(
            project_key=project_key,
            severity=severity,
            status="firing",
            summary=summary,
            description=description,
            fired_at=datetime.utcnow(),
        )
        db.add(record)
        db.flush()

        saved_projects.append({
            "project_key": project_key,
            "severity":    severity,
            "summary":     summary,
            "description": description,
            "alert_id":    int(record.id),
            # preserve payload data as fallback if cache misses
            "stale":       None,
            "wip_pct":     None,
            "total":       None,
            "done_pct":    None,
            "jira_ticket": None,
        })

        if severity == "CRITICAL":
            throttle_key = f"{project_key}:CRITICAL:ticket"

            # Only clear ticket throttle for very old unacknowledged alerts
            unacked_old = (
                db.query(AlertHistory)
                .filter(
                    AlertHistory.project_key  == project_key,
                    AlertHistory.severity     == "CRITICAL",
                    AlertHistory.status       == "firing",
                    AlertHistory.acknowledged == False,  # noqa: E712
                    AlertHistory.fired_at     <= datetime.utcnow() - timedelta(seconds=RECALL_AFTER_SECONDS),
                )
                .first()
            )
            if unacked_old:
                throttle.clear(throttle_key)

            if not throttle.is_throttled(throttle_key, seconds=RECALL_AFTER_SECONDS):
                throttle.mark(throttle_key, seconds=RECALL_AFTER_SECONDS)
                jira_ticket = incident.create_incident(
                    project_key=project_key,
                    summary=f"[AUTO-INCIDENT] {summary}",
                    description=description,
                    severity=severity,
                )
                record.jira_ticket    = jira_ticket
                record.teams_notified = True
                # store ticket in saved_projects for card display
                for p in saved_projects:
                    if p["project_key"] == project_key:
                        p["jira_ticket"] = jira_ticket
                print(f"[WEBHOOK] Ticket Jira créé : {jira_ticket} pour {project_key}")

    db.commit()

    # ── Redis accumulation ────────────────────────────────────────────────────
    acc_key = "digest:accumulator"
    merged: dict

    if _USE_REDIS and _redis_client is not None:
        existing_raw: Optional[str] = _redis_client.get(acc_key)
        existing: list = json.loads(existing_raw) if existing_raw else []
        merged = {p["project_key"]: p for p in existing}
        for p in saved_projects:
            merged[p["project_key"]] = p
        _redis_client.setex(acc_key, ACCUMULATE_WINDOW + 30, json.dumps(list(merged.values())))
        print(f"[WEBHOOK] Accumulateur → {len(merged)} projets")
    else:
        merged = {p["project_key"]: p for p in saved_projects}
        print(f"[WEBHOOK] Sans Redis — {len(merged)} projets directs")

    # ── Send digest (atomic throttle — no race condition) ─────────────────────
    digest_key = "portfolio:digest"

    if not throttle.is_throttled_or_mark(digest_key, seconds=DIGEST_THROTTLE_SECONDS):
        print(f"[WEBHOOK] Digest planifié — envoi dans {ACCUMULATE_WINDOW}s")

        async def delayed_send() -> None:
            await asyncio.sleep(ACCUMULATE_WINDOW)
            try:
                if _USE_REDIS and _redis_client is not None:
                    final_raw: Optional[str] = _redis_client.get(acc_key)
                    final_projects: list = (
                        json.loads(final_raw) if final_raw else list(merged.values())
                    )
                    _redis_client.delete(acc_key)
                else:
                    final_projects = list(merged.values())

                enriched = _enrich_with_metrics(final_projects)
                notifier.send_consolidated_digest(enriched)
                print(f"[WEBHOOK] Digest envoyé — {len(final_projects)} projets")
            except Exception as exc:
                print(f"[WEBHOOK] Erreur envoi digest : {exc}")

        asyncio.create_task(delayed_send())
    else:
        ttl_remaining = throttle.get_ttl(digest_key)
        print(f"[WEBHOOK] Digest throttlé — prochain dans ~{ttl_remaining}s")

    return JSONResponse(content={
        "processed":   len(saved_projects),
        "action":      "consolidated_digest",
        "projects":    [p["project_key"] for p in saved_projects],
        "accumulated": len(merged),
    })


# ── Metrics enrichment ────────────────────────────────────────────────────────

def _enrich_with_metrics(projects: list) -> list:
    try:
        import time
        from app.services.services import _DASHBOARD_CACHE, fetch_dashboard_data
        now = time.time()
        
        for p in projects:
            key = (p["project_key"], 30)
            cached = _DASHBOARD_CACHE.get(key)
            
            # CAS 1 : Cache frais → utiliser
            if cached and cached["expires_at"] > now:
                use_cache = True
            
            # CAS 2 : Cache vide ou expiré → essayer fetch
            else:
                try:
                    fetch_dashboard_data(p["project_key"], 30)
                    cached = _DASHBOARD_CACHE.get(key)
                    use_cache = bool(cached)
                except Exception as e:
                    print(f"[WEBHOOK] Fetch failed for {p['project_key']}: {e}")
                    # FALLBACK : utiliser cache même s'il est expiré
                    use_cache = bool(cached)
            
            # Extraire les métriques
            if use_cache and cached:
                m = cached["payload"].get("metrics", {})
                p["stale"]    = m.get("stale_in_progress_count", 0)
                p["wip_pct"]  = round(m.get("wip_ratio", 0) * 100, 1)
                p["total"]    = m.get("total", 0)
                p["done_pct"] = round(m.get("done_ratio", 0) * 100, 1)
            else:
                # FALLBACK ULTIME : valeurs par défaut pour éviter "None"
                p["stale"]    = p.get("stale", 0)
                p["wip_pct"]  = p.get("wip_pct", 0.0)
                p["total"]    = p.get("total", 0)
                p["done_pct"] = p.get("done_pct", 0.0)
                print(f"[WEBHOOK] Aucune donnée pour {p['project_key']} — fallback par défaut")
                
    except Exception as exc:
        print(f"[WEBHOOK] Enrichissement échoué : {exc}")
    return projects


# ── Acknowledge ───────────────────────────────────────────────────────────────

@router.post("/acknowledge/{alert_id}")
async def acknowledge_alert(
    alert_id:        int,
    acknowledged_by: str = "engineer",
    db:              Session = Depends(get_db),
):
    record = db.query(AlertHistory).filter(AlertHistory.id == alert_id).first()
    if not record:
        return JSONResponse(status_code=404, content={"error": "Alert not found"})
    record.acknowledged    = True
    record.acknowledged_by = acknowledged_by
    record.acknowledged_at = datetime.utcnow()
    db.commit()
    escalation.clear_pending(str(record.project_key))
    print(f"[WEBHOOK] Alert {alert_id} acquittée par {acknowledged_by}")
    return {"message": f"Alert {alert_id} acknowledged", "project": record.project_key}


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history")
async def alert_history(
    project_key: Optional[str] = None,
    limit:       int = 50,
    db:          Session = Depends(get_db),
):
    query = db.query(AlertHistory).order_by(AlertHistory.fired_at.desc())
    if project_key:
        query = query.filter(AlertHistory.project_key == project_key)
    records = query.limit(limit).all()
    return {"alerts": [r.to_dict() for r in records], "total": len(records)}


# ── Helper ────────────────────────────────────────────────────────────────────

def _handle_resolved(db: Session, project_key: str, severity: str) -> None:
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
        print(f"[WEBHOOK] Résolu — {project_key} ({severity})")