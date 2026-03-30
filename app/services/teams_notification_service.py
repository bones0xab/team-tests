# app/services/teams_notification_service.py
# ──────────────────────────────────────────────────────────────
# Upgraded Teams notifications using Adaptive Cards
# Supports: health alerts, WARNING cards, CRITICAL cards
# ──────────────────────────────────────────────────────────────

import os
import requests
from typing import Optional
from datetime import datetime


class TeamsNotificationService:

    """
    Service responsible for sending project health notifications
    to Microsoft Teams using Incoming Webhook.
    """

    def __init__(self):
        self.webhook_url = os.getenv("TEAMS_WEBHOOK_URL")

        if not self.webhook_url:
            raise ValueError(
                "TEAMS_WEBHOOK_URL is not set in environment variables."
            )


    def _send(self, card: dict) -> bool:
        """Send an Adaptive Card payload to Teams."""
        if not self.webhook_url or self.webhook_url == "disabled":
            print("[TEAMS] Webhook not configured — skipping notification")
            return False
        try:
            response = requests.post(self.webhook_url, json=card, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"[TEAMS] Failed to send notification: {e}")
            return False

    # ── Project Health Notification (existing, upgraded) ──────
    def send_project_health(
            self,
            project_name: str,
            health_status: str,
            metrics: dict | None = None,
            rules: dict | None = None,
            days_back: int = 30,
        ):
            """
            Sends a project health notification to Microsoft Teams.

            :param project_name: Name / key of the project
            :param health_status: Health status (HEALTHY / WATCH / AT_RISK)
            :param metrics: Computed metrics dict from fetch_dashboard_data
            :param rules: Rules dict (risks, actions) from fetch_dashboard_data
            :param days_back: Analysis window in days
            """

            color = self._get_color(health_status)

            # ── Core identity facts ──────────────────────────────────────────────
            facts = [
                {"name": "Project", "value": project_name},
                {"name": "Health Status", "value": health_status},
                {"name": "Analysis Window", "value": f"Last {days_back} days"},
                {
                    "name": "Timestamp",
                    "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                },
            ]

            # ── Metrics block ────────────────────────────────────────────────────
            if metrics:
                total = metrics.get("total", 0)
                done = metrics.get("done", 0)
                wip = metrics.get("wip", 0)
                stale = metrics.get("stale_in_progress_count", 0)
                done_pct = round(metrics.get("done_ratio", 0) * 100, 1)
                wip_pct = round(metrics.get("wip_ratio", 0) * 100, 1)

                facts += [
                    {"name": "Total Issues", "value": str(total)},
                    {"name": "Done", "value": f"{done} ({done_pct}%)"},
                    {"name": "In Progress (WIP)", "value": f"{wip} ({wip_pct}%)"},
                    {"name": "Stale Issues", "value": str(stale)},
                ]

            sections = [{"facts": facts, "markdown": True}]

            # ── Risks block ──────────────────────────────────────────────────────
            if rules:
                risks = rules.get("risks") or []
                actions = rules.get("actions") or []

                if risks:
                    sections.append({
                        "title": "⚠️ Risks",
                        "text": "\n\n".join(f"• {r}" for r in risks),
                        "markdown": True,
                    })
                if actions:
                    sections.append({
                        "title": "✅ Recommended Actions",
                        "text": "\n\n".join(f"• {a}" for a in actions),
                        "markdown": True,
                    })

            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "summary": f"{project_name} health status update",
                "themeColor": color,
                "title": "📊 Project Health Update",
                "sections": sections,
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to send Teams notification. "
                    f"Status code: {response.status_code}, "
                    f"Response: {response.text}"
                )

    @staticmethod
    def _get_color(status: str) -> str:
        """
        Returns color code based on health status.
        Matches rules output (HEALTHY / WATCH / AT_RISK) and legacy labels.
        """
        s = (status or "").strip().lower()

        if s in ("at_risk", "risk"):
            return "FF0000"
        if s in ("watch", "warning"):
            return "FFA500"
        if s in ("healthy",):
            return "00FF00"
        return "0076D7"

    # ── WARNING Alert (Mode A — manual approval) ──────────────
    def send_warning_alert(
        self,
        project_key: str,
        summary: str,
        description: str,
    ):
        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "⚠️ WARNING Alert",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": "warning",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Project",     "value": project_key},
                                {"title": "Summary",     "value": summary},
                                {"title": "Description", "value": description},
                                {"title": "Action",      "value": "Manual approval required"},
                            ]
                        }
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "✅ Create Incident",
                            "url": f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/incident/create?project={project_key}",
                            "style": "positive",
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "❌ Dismiss",
                            "url": f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/incident/dismiss?project={project_key}",
                            "style": "destructive",
                        }
                    ]
                }
            }]
        }
        self._send(card)

    # ── CRITICAL Alert (Mode B — auto incident created) ───────
    def send_critical_alert(
        self,
        project_key: str,
        summary: str,
        description: str,
        jira_ticket: Optional[str] = None,
        is_escalation: bool = False,
    ):
        title = "🔴 ESCALATION — Still AT RISK after 3 days" if is_escalation else "🔴 CRITICAL — Incident Auto-Created"
        color = "attention"

        jira_url = (
            f"{os.getenv('JIRA_BASE_URL', '')}/browse/{jira_ticket}"
            if jira_ticket else None
        )

        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": title,
                            "weight": "Bolder",
                            "size": "Large",
                            "color": color,
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Project",     "value": project_key},
                                {"title": "Summary",     "value": summary},
                                {"title": "Description", "value": description},
                                {"title": "Jira Ticket", "value": jira_ticket or "Not created"},
                                {"title": "Time",        "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")},
                            ]
                        }
                    ],
                    "actions": ([{
                        "type": "Action.OpenUrl",
                        "title": "🎫 View Jira Ticket",
                        "url": jira_url,
                    }] if jira_url else [])
                }
            }]
        }
        self._send(card)

    def send_daily_summary(self, projects: list[dict]):
        """
        Send a daily portfolio summary card to Teams at 9 AM.
        projects: list of {"project_key": str, "health": str}
        """
        at_risk  = [p for p in projects if p["health"] == "AT RISK"]
        warning  = [p for p in projects if p["health"] == "WARNING"]
        healthy  = [p for p in projects if p["health"] == "HEALTHY"]
        unknown  = [p for p in projects if p["health"] not in ("AT RISK", "WARNING", "HEALTHY")]

        def fmt(items):
            if not items:
                return "None"
            return ", ".join(p["project_key"] for p in items)

        today = datetime.utcnow().strftime("%B %d, %Y")

        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"📊 Daily Project Health Summary — {today}",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": "accent",
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Portfolio overview across {len(projects)} active projects.",
                            "isSubtle": True,
                            "spacing": "Small",
                        },
                        {"type": "Separator"},
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": f"🔴 AT RISK ({len(at_risk)})",  "value": fmt(at_risk)},
                                {"title": f"⚠️ WARNING ({len(warning)})",  "value": fmt(warning)},
                                {"title": f"✅ HEALTHY ({len(healthy)})",   "value": fmt(healthy)},
                            ]
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Generated at 09:00 AM — Africa/Casablanca",
                            "isSubtle": True,
                            "size": "Small",
                            "spacing": "Medium",
                        }
                    ],
                    "actions": [{
                        "type": "Action.OpenUrl",
                        "title": "📈 Open Dashboard",
                        "url": os.getenv("APP_URL", "http://localhost:5173"),
                    }]
                }
            }]
        }
        self._send(card)