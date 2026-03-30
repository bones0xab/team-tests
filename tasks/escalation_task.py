# app/tasks/escalation_task.py

import asyncio
from datetime import datetime, timedelta

from app.db.session import SessionLocal
from app.db.models_alerts import AlertHistory
from app.services.teams_notification_service import TeamsNotificationService
from app.services.incident_service import IncidentService
from app.services.throttle_service import EscalationService

escalation = EscalationService()


async def escalation_worker() -> None:
    """Runs forever — escalates unacknowledged WARNING alerts after 15 minutes."""
    print("[ESCALATION] Worker started")

    while True:
        await asyncio.sleep(60)
        db = SessionLocal()  # always assigned — no longer possibly unbound
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=15)

            pending = (
                db.query(AlertHistory)
                .filter(
                    AlertHistory.severity     == "WARNING",
                    AlertHistory.status       == "firing",
                    AlertHistory.acknowledged == False,  # noqa: E712
                    AlertHistory.fired_at     <= cutoff,
                )
                .all()
            )

            for alert in pending:
                project_key = str(alert.project_key)
                summary     = str(alert.summary or "No summary")

                print(f"[ESCALATION] {project_key} WARNING → CRITICAL (no ack in 15min)")

                notifier = TeamsNotificationService()
                incident = IncidentService()

                jira_ticket = incident.create_incident(
                    project_key = project_key,
                    summary     = f"[ESCALATED] {summary}",
                    description = (
                        f"WARNING alert was not acknowledged within 15 minutes.\n"
                        f"Original: {summary}\n"
                        f"Fired at: {alert.fired_at}"
                    ),
                    severity = "CRITICAL",
                )

                notifier.send_critical_alert(
                    project_key = project_key,
                    summary     = f"[ESCALATED] {summary}",
                    description = "Not acknowledged in 15 min — auto-escalated to CRITICAL",
                    jira_ticket = jira_ticket,
                )

                alert.severity    = "CRITICAL"
                alert.jira_ticket = jira_ticket
                db.commit()

                escalation.clear_pending(project_key)

        except Exception as e:
            print(f"[ESCALATION] Error: {e}")
        finally:
            db.close()  # always runs — db is always bound